"""Unit tests for attachment domain invariants."""

from datetime import datetime, timezone

import pytest

from app.domains.notes.domain.models import (
    NoteAttachment,
    NoteProcessingStatus,
)


def make_attachment(**overrides) -> NoteAttachment:
    """Create a valid Notes Library attachment for model tests."""

    now = datetime.now(timezone.utc)
    values = {
        "attachment_id": 1,
        "uploaded_by": "user-1",
        "title": "Architecture",
        "file_name": "architecture.pdf",
        "file_type": "application/pdf",
        "file_size_bytes": 100,
        "object_path": "/private/one.pdf",
        "processing_status": NoteProcessingStatus.QUEUED,
        "processing_progress": 0,
        "uploaded_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return NoteAttachment(**values)


def test_library_flag_controls_my_notes_visibility() -> None:
    attachment = make_attachment()

    assert attachment.appears_in_my_notes is True


def test_personal_chat_attachment_can_appear_in_my_notes() -> None:
    attachment = make_attachment(channel_id="personal-chat-1", message_id=7)

    assert attachment.appears_in_my_notes is True


def test_group_channel_attachment_does_not_appear_in_my_notes() -> None:
    attachment = make_attachment(
        channel_id="group-channel-1",
        message_id=7,
        show_in_library=False,
    )

    assert attachment.appears_in_my_notes is False


def test_message_without_channel_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot have a message_id"):
        make_attachment(message_id=7)


def test_hidden_attachment_without_channel_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires a channel_id"):
        make_attachment(show_in_library=False)


def test_ready_attachment_requires_full_progress() -> None:
    with pytest.raises(ValueError, match="must have 100"):
        make_attachment(
            processing_status=NoteProcessingStatus.READY,
            processing_progress=90,
        )


def test_failed_attachment_requires_safe_error() -> None:
    with pytest.raises(ValueError, match="must include"):
        make_attachment(
            processing_status=NoteProcessingStatus.FAILED,
            processing_progress=30,
        )
