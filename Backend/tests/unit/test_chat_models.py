"""Unit tests for personal-chat domain invariants."""

from datetime import datetime, timezone

import pytest

from app.domains.chats.domain.models import (
    ChatMessage,
    ChatMessageRole,
    ChatMessageStatus,
    ChatSource,
    PersonalChat,
)


def test_personal_chat_requires_owner_and_title() -> None:
    """Reject conversations that cannot be owned or displayed."""

    now = datetime.now(timezone.utc)

    with pytest.raises(ValueError, match="owner_id"):
        PersonalChat(
            chat_id="chat-1",
            owner_id=" ",
            title="New chat",
            created_at=now,
            updated_at=now,
        )


def test_only_assistant_messages_may_have_sources() -> None:
    """Prevent a user message from claiming AI citations."""

    source = ChatSource(
        note_id=1,
        note_title="Databases",
        chunk_id=2,
        page=3,
    )

    with pytest.raises(ValueError, match="assistant"):
        ChatMessage(
            message_id=1,
            chat_id="chat-1",
            role=ChatMessageRole.USER,
            content="What is indexing?",
            status=ChatMessageStatus.COMPLETED,
            created_at=datetime.now(timezone.utc),
            sources=(source,),
        )


def test_source_page_must_be_positive_when_present() -> None:
    """Reject impossible page-number citations."""

    with pytest.raises(ValueError, match="page"):
        ChatSource(
            note_id=1,
            note_title="Databases",
            chunk_id=2,
            page=0,
        )

