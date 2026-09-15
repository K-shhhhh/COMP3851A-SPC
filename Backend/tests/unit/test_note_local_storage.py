"""Unit tests for private local attachment storage."""

from pathlib import Path

import pytest

from app.domains.notes.domain.exceptions import AttachmentStorageError
from app.domains.notes.infrastructure.local_storage import (
    LocalAttachmentStorage,
)


@pytest.mark.asyncio
async def test_pdf_can_be_stored_read_and_deleted(tmp_path: Path) -> None:
    storage = LocalAttachmentStorage(tmp_path)
    data = b"%PDF-1.7\nsample"

    object_path = await storage.store_pdf(data)

    assert Path(object_path).parent == tmp_path.resolve()
    assert await storage.read_pdf(object_path) == data
    assert await storage.delete_pdf(object_path) is True
    assert not Path(object_path).exists()


@pytest.mark.asyncio
async def test_storage_generates_unique_pdf_names(tmp_path: Path) -> None:
    storage = LocalAttachmentStorage(tmp_path)

    first = await storage.store_pdf(b"%PDF-1.7\nfirst")
    second = await storage.store_pdf(b"%PDF-1.7\nsecond")

    assert first != second
    assert Path(first).suffix == ".pdf"
    assert Path(second).suffix == ".pdf"


@pytest.mark.asyncio
async def test_storage_rejects_empty_content(tmp_path: Path) -> None:
    storage = LocalAttachmentStorage(tmp_path)

    with pytest.raises(AttachmentStorageError):
        await storage.store_pdf(b"")


@pytest.mark.asyncio
async def test_storage_rejects_path_outside_root(tmp_path: Path) -> None:
    storage = LocalAttachmentStorage(tmp_path / "notes")
    outside = tmp_path / "private.pdf"
    outside.write_bytes(b"%PDF-1.7\nprivate")

    with pytest.raises(AttachmentStorageError):
        await storage.read_pdf(str(outside))


@pytest.mark.asyncio
async def test_deleting_missing_safe_path_returns_false(
    tmp_path: Path,
) -> None:
    storage = LocalAttachmentStorage(tmp_path)

    assert await storage.delete_pdf(str(tmp_path / "missing.pdf")) is False
