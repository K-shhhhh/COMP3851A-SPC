# AI extension point: extract document text and metadata.
# Owner: Krish
#
# Ported from rag_pipeline.ipynb. Text/table extraction is unchanged from the
# notebook version. Images are safety-checked (NudeNet) then captioned via a
# vision model, so they flow into chunking as plain text like everything else.

import os
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

_detector = NudeDetector()

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
)
VISION_MODEL = "openrouter/free"  # auto-picks an available free vision model


def is_image_safe(image_bytes: bytes) -> bool:
    temp_path = "/tmp/_nudenet_check.jpg"
    with open(temp_path, "wb") as f:
        f.write(image_bytes)
    detections = _detector.detect(temp_path)
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
            return response.choices[0].message.content
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 1s, then 2s between retries

    # All retries exhausted -- don't let one bad image kill the whole upload.
    print(f"Warning: image captioning failed after {max_retries} attempts ({last_error}); using a placeholder caption instead.")
    return "[An image appears on this page. It could not be automatically captioned due to a temporary AI service error.]"


def extract_structured_pdf(file_path: str, image_mode: str = "strict") -> List[Dict]:
    """
    Extracts text, tables, and images (captioned) from a PDF, one page at a time.

    image_mode="strict": one unsafe image anywhere rejects the whole PDF (raises ValueError).
    image_mode="lenient": unsafe images are skipped and logged; the rest of the PDF still processes.
    """
    assert image_mode in ("strict", "lenient")
    doc = fitz.open(file_path)
    pages_out = []
    flagged_images = []

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
            image_bytes = doc.extract_image(xref)["image"]
            if not is_image_safe(image_bytes):
                if image_mode == "strict":
                    raise ValueError(f"Unsafe image detected on page {page_num} -- PDF rejected entirely.")
                else:
                    flagged_images.append({"page_num": page_num, "xref": xref})
                    continue
            caption = caption_image(image_bytes)
            pages_out.append({"page_num": page_num, "content": caption, "type": "image"})

    if image_mode == "lenient" and flagged_images:
        print(f"Warning: {len(flagged_images)} image(s) flagged and skipped: {flagged_images}")

    return pages_out
