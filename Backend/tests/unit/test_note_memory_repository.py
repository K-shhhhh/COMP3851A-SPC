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
    show_in_library: bool = True,
):
    """Create one queued attachment for repository tests."""

    return await repository.create_attachment(
        uploaded_by=user_id,
        title="Test note",
        file_name="test.pdf",
        file_type="application/pdf",
        file_size_bytes=100,
        object_path="/private/test.pdf",
        show_in_library=show_in_library,
        channel_id=channel_id,
        message_id=message_id,
    )


async def test_create_assigns_identifier_and_queued_state() -> None:
    repository = InMemoryAttachmentRepository()

    attachment = await create_attachment(repository)

    assert attachment.attachment_id == 1
    assert attachment.processing_status == NoteProcessingStatus.QUEUED
    assert attachment.processing_progress == 0


async def test_my_notes_uses_explicit_visibility_flag() -> None:
    repository = InMemoryAttachmentRepository()
    await create_attachment(repository)
    await create_attachment(
        repository,
        channel_id="channel-1",
        message_id=1,
        show_in_library=False,
    )

    items, total = await repository.list_note_library_attachments(
        user_id="user-1",
        offset=0,
        limit=20,
    )

    assert total == 1
    assert len(items) == 1
    assert items[0].show_in_library is True


async def test_personal_chat_attachment_appears_in_my_notes() -> None:
    repository = InMemoryAttachmentRepository()
    attachment = await create_attachment(
        repository,
        channel_id="personal-chat-1",
        show_in_library=True,
    )

    items, total = await repository.list_note_library_attachments(
        user_id="user-1",
        offset=0,
        limit=20,
    )

    assert total == 1
    assert items == [attachment]


async def test_direct_channel_attachment_does_not_require_message() -> None:
    repository = InMemoryAttachmentRepository()

    attachment = await create_attachment(
        repository,
        channel_id="channel-1",
        message_id=None,
        show_in_library=False,
    )

    assert attachment.channel_id == "channel-1"
    assert attachment.message_id is None
    assert attachment.appears_in_my_notes is False


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

    processing = await repository.update_processing_status(
        attachment_id=attachment.attachment_id,
        processing_status=NoteProcessingStatus.PROCESSING,
        processing_progress=10,
    )
    updated = await repository.update_processing_status(
        attachment_id=attachment.attachment_id,
        processing_status=NoteProcessingStatus.READY,
        processing_progress=100,
    )

    assert processing is not None
    assert processing.processing_started_at is not None
    assert processing.processing_completed_at is None
    assert updated is not None
    assert updated.processing_status == NoteProcessingStatus.READY
    assert updated.processing_started_at == processing.processing_started_at
    assert updated.processing_completed_at is not None
    assert updated.processing_completed_at >= updated.processing_started_at


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
