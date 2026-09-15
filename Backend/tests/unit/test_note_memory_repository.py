"""Unit tests for the temporary attachment metadata repository."""

import pytest

from app.domains.notes.domain.models import NoteProcessingStatus
from app.domains.notes.infrastructure.memory_repository import (
    InMemoryAttachmentRepository,
)


pytestmark = pytest.mark.asyncio


async def create_attachment(
    repository: InMemoryAttachmentRepository,
    *,
    user_id: str = "user-1",
    channel_id: str | None = None,
    message_id: int | None = None,
):
    """Create one queued attachment for repository tests."""

    return await repository.create_attachment(
        uploaded_by=user_id,
        title="Test note",
        file_name="test.pdf",
        file_type="application/pdf",
        file_size_bytes=100,
        object_path="/private/test.pdf",
        channel_id=channel_id,
        message_id=message_id,
    )


async def test_create_assigns_identifier_and_queued_state() -> None:
    repository = InMemoryAttachmentRepository()

    attachment = await create_attachment(repository)

    assert attachment.attachment_id == 1
    assert attachment.processing_status == NoteProcessingStatus.QUEUED
    assert attachment.processing_progress == 0


async def test_my_notes_excludes_message_attachments() -> None:
    repository = InMemoryAttachmentRepository()
    await create_attachment(repository)
    await create_attachment(
        repository,
        channel_id="channel-1",
        message_id=1,
    )

    items, total = await repository.list_note_library_attachments(
        user_id="user-1",
        offset=0,
        limit=20,
    )

    assert total == 1
    assert len(items) == 1
    assert items[0].channel_id is None


async def test_owned_lookup_prevents_cross_user_access() -> None:
    repository = InMemoryAttachmentRepository()
    attachment = await create_attachment(repository, user_id="user-1")

    inaccessible = await repository.get_owned_attachment(
        attachment_id=attachment.attachment_id,
        user_id="user-2",
    )

    assert inaccessible is None


async def test_worker_can_update_processing_state() -> None:
    repository = InMemoryAttachmentRepository()
    attachment = await create_attachment(repository)

    updated = await repository.update_processing_status(
        attachment_id=attachment.attachment_id,
        processing_status=NoteProcessingStatus.READY,
        processing_progress=100,
    )

    assert updated is not None
    assert updated.processing_status == NoteProcessingStatus.READY


async def test_soft_deleted_attachment_is_no_longer_returned() -> None:
    from datetime import datetime, timezone

    repository = InMemoryAttachmentRepository()
    attachment = await create_attachment(repository)

    deleted = await repository.soft_delete_owned_attachment(
        attachment_id=attachment.attachment_id,
        user_id="user-1",
        deleted_at=datetime.now(timezone.utc),
    )

    assert deleted is True
    assert await repository.get_attachment_by_id(
        attachment.attachment_id
    ) is None
