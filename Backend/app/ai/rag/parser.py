# AI extension point: extract document text and metadata.
# Owner: Krish
#
# Ported from rag_pipeline.ipynb. Text/table extraction is unchanged from the
# notebook version. Images are safety-checked (NudeNet) then captioned via a
# vision model, so they flow into chunking as plain text like everything else.

import logging
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv, find_dotenv

# loads the repo-root .env even when this module is imported from elsewhere
# (e.g. Backend/) -- find_dotenv() walks upward until it finds one
load_dotenv(find_dotenv(usecwd=True))
import time
import base64
from typing import List, Dict

import fitz
from nudenet import NudeDetector
from openai import OpenAI

logger = logging.getLogger(__name__)

_detector = NudeDetector()

# Images with either side shorter than this are almost always decorative
# (icons, bullets, divider lines, logos). Captioning them costs a safety
# check plus a vision-model round trip each, and the junk captions they
# produce pollute search results. Real diagrams and charts are far larger.
MIN_IMAGE_DIMENSION_PX = 100


def _env_int(name: str, default: int, minimum: int) -> int:
    """Read a whole number setting from the environment, falling back safely."""

    try:
        value = int(os.environ.get(name, default))
    except ValueError:
        return default
    return max(minimum, value)


# Describing a picture costs one slow vision model call (10 to 20 seconds on the
# free tier). A slide deck with 30 figures used to take about 7 minutes and kept
# a worker busy the whole time, so every other upload queued behind it. Only the
# largest pictures, which carry the most information, are described.
MAX_CAPTIONED_IMAGES = _env_int("MAX_CAPTIONED_IMAGES", 8, 0)

# The descriptions are network bound, so a few can run at the same time.
CAPTION_WORKERS = _env_int("CAPTION_WORKERS", 3, 1)

UNSAFE_LABELS = {
    "EXPOSED_BREAST_F",
    "EXPOSED_GENITALIA_F",
    "EXPOSED_GENITALIA_M",
    "EXPOSED_BUTTOCKS",
    "EXPOSED_ANUS",
}
CONFIDENCE_THRESHOLD = 0.5

_client = OpenAI(
    base_url=os.environ.get("INFERENCE_API_URL") or "https://openrouter.ai/api/v1",
    api_key=os.environ.get("INFERENCE_API_KEY"),
    # One slow call must not hold a worker for minutes. caption_image retries
    # by itself, so the client does not retry on top of that.
    timeout=45.0,
    max_retries=0,
)
VISION_MODEL = "openrouter/free"  # auto-picks an available free vision model


def is_image_safe(image_bytes: bytes) -> bool:
    # Every check gets its own temp file. Worker processes run side by side, and
    # one fixed file name let them overwrite and delete each other's images.
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as handle:
        handle.write(image_bytes)
        temp_path = handle.name
    try:
        detections = _detector.detect(temp_path)
    finally:
        os.remove(temp_path)
    for det in detections:
        if det["class"] in UNSAFE_LABELS and det["score"] >= CONFIDENCE_THRESHOLD:
            return False
    return True


def caption_image(image_bytes: bytes, max_retries: int = 3) -> str:
    """
    Captions an image via a free-tier vision model. Free-tier model
    availability is unreliable (rate limits, provider-side rejections) --
    retries with backoff first, then degrades gracefully with a placeholder
    rather than failing the ENTIRE document over one flaky image call.
    """
    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    data_uri = f"data:image/jpeg;base64,{b64_image}"

    last_error = None
    for attempt in range(max_retries):
        try:
            response = _client.chat.completions.create(
                model=VISION_MODEL,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this image in detail. If it is a diagram, chart, or table, describe its structure and the information it conveys, not just what it looks like."},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                }],
            )
            content = response.choices[0].message.content
            if content and content.strip():
                return content.strip()
            # Some free models answer with no text at all. Returning that would
            # crash the text splitter later, so treat it as a failed attempt.
            last_error = ValueError("the vision model returned an empty description")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 1s, then 2s between retries

    # All retries exhausted -- don't let one bad image kill the whole upload.
    print(f"Warning: image captioning failed after {max_retries} attempts ({last_error}); using a placeholder caption instead.")
    return "[An image appears on this page. It could not be automatically captioned due to a temporary AI service error.]"


def _image_area(candidate: Dict) -> int:
    return candidate["area"]


def _page_then_xref(candidate: Dict):
    return (candidate["page_num"], candidate["xref"])


def _page_number(entry: Dict) -> int:
    return entry["page_num"]


def extract_structured_pdf(file_path: str, image_mode: str = "strict") -> List[Dict]:
    """
    Extracts text, tables, and images (captioned) from a PDF, one page at a time.

    image_mode="strict": one unsafe image anywhere rejects the whole PDF (raises ValueError).
    image_mode="lenient": unsafe images are skipped and logged; the rest of the PDF still processes.

    EVERY distinct image gets the safety check, whatever its size or rank. Only the
    AI description is limited to the MAX_CAPTIONED_IMAGES largest safe images,
    and those descriptions are requested a few at a time.
    """
    assert image_mode in ("strict", "lenient")
    doc = fitz.open(file_path)
    pages_out = []
    flagged_images = []
    candidates = []
    seen_xrefs = set()
    skipped_duplicate = 0
    skipped_small = 0

    for page_index, page in enumerate(doc):
        page_num = page_index + 1

        tables = page.find_tables()
        if tables.tables:
            for table in tables:
                table_data = table.extract()
                rows = []
                for row in table_data:
                    clean_row = [str(cell).strip() for cell in row if cell is not None]
                    rows.append(" | ".join(clean_row))
                pages_out.append({"page_num": page_num, "content": "\n".join(rows), "type": "table"})
        else:
            text = page.get_text()
            if text.strip():
                pages_out.append({"page_num": page_num, "content": text, "type": "text"})

        for img in page.get_images(full=True):
            xref = img[0]
            width, height = img[2], img[3]

            # The same image (e.g. a header logo) is listed again on every
            # page it appears on: process each distinct image only once.
            if xref in seen_xrefs:
                skipped_duplicate += 1
                continue
            seen_xrefs.add(xref)

            # Decide cheaply from the metadata, before extracting the image
            # or running the safety check and the vision model on it.
            if width < MIN_IMAGE_DIMENSION_PX or height < MIN_IMAGE_DIMENSION_PX:
                skipped_small += 1
                continue

            candidates.append({"page_num": page_num, "xref": xref, "area": width * height})

    # Safety check on every candidate: fast, local, one at a time.
    safe_candidates = []
    for candidate in sorted(candidates, key=_page_then_xref):
        image_bytes = doc.extract_image(candidate["xref"])["image"]
        if not is_image_safe(image_bytes):
            if image_mode == "strict":
                raise ValueError(f"Unsafe image detected on page {candidate['page_num']} -- PDF rejected entirely.")
            flagged_images.append({"page_num": candidate["page_num"], "xref": candidate["xref"]})
            continue
        safe_candidates.append(candidate)

    # Describe only the largest ones: they carry the most information.
    skipped_over_limit = 0
    if len(safe_candidates) > MAX_CAPTIONED_IMAGES:
        largest_first = sorted(safe_candidates, key=_image_area, reverse=True)
        chosen = largest_first[:MAX_CAPTIONED_IMAGES]
        skipped_over_limit = len(safe_candidates) - len(chosen)
    else:
        chosen = list(safe_candidates)
    chosen.sort(key=_page_then_xref)

    # The descriptions are network bound, so a few run at the same time.
    captioned = 0
    if chosen:
        with ThreadPoolExecutor(max_workers=CAPTION_WORKERS) as pool:
            futures = []
            for candidate in chosen:
                image_bytes = doc.extract_image(candidate["xref"])["image"]
                futures.append(pool.submit(caption_image, image_bytes))
            for candidate, future in zip(chosen, futures):
                pages_out.append({"page_num": candidate["page_num"], "content": future.result(), "type": "image"})
                captioned += 1

    # Stable sort: a page's text and tables stay in front of its pictures.
    pages_out.sort(key=_page_number)

    logger.info(
        "Image processing: %d captioned, %d skipped to stay within the limit of %d, "
        "%d skipped as duplicates, %d skipped as too small",
        captioned,
        skipped_over_limit,
        MAX_CAPTIONED_IMAGES,
        skipped_duplicate,
        skipped_small,
    )

    if image_mode == "lenient" and flagged_images:
        print(f"Warning: {len(flagged_images)} image(s) flagged and skipped: {flagged_images}")

    return pages_out
