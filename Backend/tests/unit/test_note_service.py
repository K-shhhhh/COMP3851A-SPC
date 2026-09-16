"""Unit tests for Notes application use cases."""

from pathlib import Path

import pytest

from app.domains.notes.application.services import NoteService
from app.domains.notes.domain.exceptions import (
    AttachmentNotFoundError,
    EmptyFileError,
    FileTooLargeError,
    InvalidPdfError,
    UnsupportedFileTypeError,
)
from app.domains.notes.infrastructure.local_storage import (
    LocalAttachmentStorage,
)
from app.domains.notes.infrastructure.memory_processing import (
    InMemoryAttachmentProcessingDispatcher,
)
from app.domains.notes.infrastructure.memory_repository import (
    InMemoryAttachmentRepository,
)


pytestmark = pytest.mark.asyncio


def make_service(tmp_path: Path, maximum_size: int = 1024):
    """Create isolated Notes dependencies for one test."""

    repository = InMemoryAttachmentRepository()
    storage = LocalAttachmentStorage(tmp_path)
    dispatcher = InMemoryAttachmentProcessingDispatcher()
    service = NoteService(
        repository=repository,
        storage=storage,
        processing_dispatcher=dispatcher,
        maximum_file_size_bytes=maximum_size,
    )
    return service, repository, dispatcher


async def test_upload_stores_metadata_and_dispatches_processing(
    tmp_path: Path,
) -> None:
    service, _, dispatcher = make_service(tmp_path)

    attachment = await service.upload_note(
        user_id="user-1",
        original_filename="lecture.pdf",
        content_type="application/pdf",
        data=b"%PDF-1.7\nlecture",
        title=" Lecture One ",
    )

    assert attachment.uploaded_by == "user-1"
    assert attachment.title == "Lecture One"
    assert attachment.channel_id is None
    assert Path(attachment.object_path).exists()
    assert dispatcher.requests == (
        (attachment.attachment_id, attachment.object_path),
    )


async def test_upload_defaults_title_to_filename(tmp_path: Path) -> None:
    service, _, _ = make_service(tmp_path)

    attachment = await service.upload_note(
        user_id="user-1",
        original_filename="software architecture.pdf",
        content_type="application/pdf",
        data=b"%PDF-1.7\nlecture",
    )

    assert attachment.title == "software architecture"


@pytest.mark.parametrize(
    ("content_type", "data", "error_type"),
    [
        ("text/plain", b"%PDF-1.7\ntext", UnsupportedFileTypeError),
        ("application/pdf", b"", EmptyFileError),
        ("application/pdf", b"not a pdf", InvalidPdfError),
    ],
)
async def test_invalid_uploads_are_rejected(
    tmp_path: Path,
    content_type: str,
    data: bytes,
    error_type: type[Exception],
) -> None:
    service, _, _ = make_service(tmp_path)

    with pytest.raises(error_type):
        await service.upload_note(
            user_id="user-1",
            original_filename="lecture.pdf",
            content_type=content_type,
            data=data,
        )


async def test_oversized_upload_is_rejected(tmp_path: Path) -> None:
    service, _, _ = make_service(tmp_path, maximum_size=8)

    with pytest.raises(FileTooLargeError):
        await service.upload_note(
            user_id="user-1",
            original_filename="lecture.pdf",
            content_type="application/pdf",
            data=b"%PDF-1.7\nlarge",
        )


async def test_list_and_get_are_scoped_to_owner(tmp_path: Path) -> None:
    service, _, _ = make_service(tmp_path)
    attachment = await service.upload_note(
        user_id="user-1",
        original_filename="lecture.pdf",
        content_type="application/pdf",
        data=b"%PDF-1.7\nlecture",
    )

    items, total = await service.list_notes(
        user_id="user-1",
        page=1,
        page_size=20,
    )

    assert total == 1
    assert items == [attachment]

    with pytest.raises(AttachmentNotFoundError):
        await service.get_note(
            attachment_id=attachment.attachment_id,
            user_id="user-2",
        )


async def test_delete_removes_owned_note_and_file(tmp_path: Path) -> None:
    service, _, _ = make_service(tmp_path)
    attachment = await service.upload_note(
        user_id="user-1",
        original_filename="lecture.pdf",
        content_type="application/pdf",
        data=b"%PDF-1.7\nlecture",
    )

    await service.delete_note(
        attachment_id=attachment.attachment_id,
        user_id="user-1",
    )

    assert not Path(attachment.object_path).exists()
    with pytest.raises(AttachmentNotFoundError):
        await service.get_note(
            attachment_id=attachment.attachment_id,
            user_id="user-1",
        )
