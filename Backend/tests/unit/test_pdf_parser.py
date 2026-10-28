"""Tests for the PDF parser: page text, tables, picture handling and safety.

The safety model and the vision model are replaced with fakes, so these tests
are fast and need no network.
"""

import threading
import time

import fitz
import pytest

from app.ai.rag import parser


def _picture(width, height, shade):
    """Return PNG bytes of a plain coloured picture."""
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, width, height), False)
    pix.set_rect(pix.irect, (shade, 120, 200))
    return pix.tobytes("png")


def _build_pdf(path, pictures_per_page, with_table_page=False):
    """Save a PDF where page N has the given number of distinct pictures."""
    doc = fitz.open()
    shade = 10
    for page_index, count in enumerate(pictures_per_page):
        page = doc.new_page()
        page.insert_text((50, 50), f"Page {page_index + 1} prose about topic {page_index}.")
        for k in range(count):
            shade += 7
            page.insert_image(
                fitz.Rect(50, 100 + k * 120, 250 + k * 40, 200 + k * 120),
                stream=_picture(400 + k * 300, 300 + k * 200, shade % 255),
            )
    if with_table_page:
        page = doc.new_page()
        page.insert_text((50, 50), "Results discussion. The forest uses 134 trees.")
        top, left, cell_w, cell_h = 100, 50, 120, 25
        values = [["Model", "RMSE"], ["Network", "0.029"], ["Forest", "0.031"]]
        for r in range(4):
            page.draw_line((left, top + r * cell_h), (left + 2 * cell_w, top + r * cell_h))
        for c in range(3):
            page.draw_line((left + c * cell_w, top), (left + c * cell_w, top + 3 * cell_h))
        for r, row in enumerate(values):
            for c, value in enumerate(row):
                page.insert_text((left + c * cell_w + 5, top + r * cell_h + 17), value)
    doc.save(path)


@pytest.fixture
def fakes(monkeypatch):
    """Replace the safety check and the vision model; record what they saw."""
    seen = {"safety": [], "captions": [], "mimes": [], "threads": set()}

    def fake_safe(image_bytes):
        seen["safety"].append(image_bytes)
        return True

    def fake_caption(image_bytes, max_retries=3, mime_type="image/jpeg"):
        seen["captions"].append(image_bytes)
        seen["mimes"].append(mime_type)
        seen["threads"].add(threading.get_ident())
        return "A described picture."

    monkeypatch.setattr(parser, "is_image_safe", fake_safe)
    monkeypatch.setattr(parser, "caption_image", fake_caption)
    return seen


def test_page_with_a_table_keeps_its_text(tmp_path, fakes):
    path = str(tmp_path / "table.pdf")
    _build_pdf(path, [0], with_table_page=True)

    entries = parser.extract_structured_pdf(path)

    page_two = [entry for entry in entries if entry["page_num"] == 2]
    kinds = {entry["type"] for entry in page_two}
    assert kinds == {"text", "table"}
    text = next(entry["content"] for entry in page_two if entry["type"] == "text")
    assert "134 trees" in text          # prose outside the table is not lost
    table = next(entry["content"] for entry in page_two if entry["type"] == "table")
    assert "Network" in table and "Forest" in table


def test_pages_without_drawings_skip_table_search(tmp_path, fakes, monkeypatch):
    path = str(tmp_path / "pictures.pdf")
    _build_pdf(path, [1, 1, 1])
    calls = {"count": 0}
    original = fitz.Page.find_tables

    def counting_find_tables(self, *args, **kwargs):
        calls["count"] += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(fitz.Page, "find_tables", counting_find_tables)

    parser.extract_structured_pdf(path)

    assert calls["count"] == 0


def test_every_picture_is_checked_and_only_the_largest_are_described(tmp_path, fakes, monkeypatch):
    monkeypatch.setattr(parser, "MAX_CAPTIONED_IMAGES", 2)
    path = str(tmp_path / "many.pdf")
    _build_pdf(path, [2, 2, 1])   # five distinct pictures

    entries = parser.extract_structured_pdf(path)

    assert len(fakes["safety"]) == 5
    image_entries = [entry for entry in entries if entry["type"] == "image"]
    assert len(image_entries) == 2
    # the second picture on a page is the larger one in _build_pdf
    pages = sorted(entry["page_num"] for entry in image_entries)
    assert pages == [1, 2]


def test_pictures_are_shrunk_and_sent_as_jpeg(tmp_path, fakes, monkeypatch):
    monkeypatch.setattr(parser, "MAX_IMAGE_SIDE_PX", 320)
    path = str(tmp_path / "big.pdf")
    _build_pdf(path, [2])          # the larger picture is 700 x 500

    parser.extract_structured_pdf(path)

    assert set(fakes["mimes"]) == {"image/jpeg"}
    for image_bytes in fakes["captions"]:
        pix = fitz.Pixmap(image_bytes)
        assert max(pix.width, pix.height) <= 320


def test_unsafe_picture_rejects_the_pdf_in_strict_mode(tmp_path, fakes, monkeypatch):
    path = str(tmp_path / "unsafe.pdf")
    _build_pdf(path, [1, 1])
    checked = {"count": 0}

    def second_is_unsafe(image_bytes):
        checked["count"] += 1
        return checked["count"] != 2

    monkeypatch.setattr(parser, "is_image_safe", second_is_unsafe)

    with pytest.raises(ValueError):
        parser.extract_structured_pdf(path, image_mode="strict")


def test_unsafe_picture_is_skipped_in_lenient_mode(tmp_path, fakes, monkeypatch):
    path = str(tmp_path / "lenient.pdf")
    _build_pdf(path, [1, 1])
    checked = {"count": 0}

    def first_is_unsafe(image_bytes):
        checked["count"] += 1
        return checked["count"] != 1

    monkeypatch.setattr(parser, "is_image_safe", first_is_unsafe)

    entries = parser.extract_structured_pdf(path, image_mode="lenient")

    image_entries = [entry for entry in entries if entry["type"] == "image"]
    assert len(image_entries) == 1
    assert len(fakes["captions"]) == 1


def test_descriptions_run_while_text_is_extracted(tmp_path, monkeypatch):
    """The slow description calls overlap with the text work instead of following it."""
    monkeypatch.setattr(parser, "is_image_safe", lambda image_bytes: True)

    def slow_caption(image_bytes, max_retries=3, mime_type="image/jpeg"):
        time.sleep(0.5)
        return "A described picture."

    monkeypatch.setattr(parser, "caption_image", slow_caption)
    monkeypatch.setattr(parser, "CAPTION_WORKERS", 3)
    path = str(tmp_path / "overlap.pdf")
    _build_pdf(path, [1, 1, 1])

    started = time.perf_counter()
    entries = parser.extract_structured_pdf(path)
    elapsed = time.perf_counter() - started

    assert len([entry for entry in entries if entry["type"] == "image"]) == 3
    assert elapsed < 1.4   # three 0.5s descriptions in parallel, not 1.5s in a row


def test_entries_stay_in_page_order(tmp_path, fakes):
    path = str(tmp_path / "order.pdf")
    _build_pdf(path, [1, 0, 1])

    entries = parser.extract_structured_pdf(path)

    pages = [entry["page_num"] for entry in entries]
    assert pages == sorted(pages)
    first_page = [entry["type"] for entry in entries if entry["page_num"] == 1]
    assert first_page == ["text", "image"]
