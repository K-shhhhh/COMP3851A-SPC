"""Unit tests for temporary in-memory personal-chat persistence."""

import pytest

from app.domains.chats.domain.models import ChatMessageRole
from app.domains.chats.infrastructure.memory_repository import (
    InMemoryChatRepository,
)


pytestmark = pytest.mark.asyncio


async def test_chat_crud_is_scoped_to_owner() -> None:
    """Create, rename, list, and delete without cross-user exposure."""

    repository = InMemoryChatRepository()
    chat = await repository.create_chat(
        owner_id="user-1",
        title="New chat",
    )

    assert await repository.get_owned_chat(
        chat_id=chat.chat_id,
        owner_id="user-2",
    ) is None

    renamed = await repository.rename_owned_chat(
        chat_id=chat.chat_id,
        owner_id="user-1",
        title="Database questions",
    )
    assert renamed is not None
    assert renamed.title == "Database questions"

    items, total = await repository.list_owned_chats(
        owner_id="user-1",
        offset=0,
        limit=20,
    )
    assert total == 1
    assert items[0].chat_id == chat.chat_id


async def test_messages_are_oldest_first_and_update_preview() -> None:
    """Persist ordered history and the latest sidebar preview."""

    repository = InMemoryChatRepository()
    chat = await repository.create_chat(
        owner_id="user-1",
        title="New chat",
    )
    first = await repository.create_message(
        chat_id=chat.chat_id,
        role=ChatMessageRole.USER,
        content="What is an index?",
    )
    second = await repository.create_message(
        chat_id=chat.chat_id,
        role=ChatMessageRole.ASSISTANT,
        content="An index speeds up selected lookups.",
    )

    messages, total = await repository.list_messages(
        chat_id=chat.chat_id,
        offset=0,
        limit=50,
    )
    updated = await repository.get_owned_chat(
        chat_id=chat.chat_id,
        owner_id="user-1",
    )

    assert total == 2
    assert messages == [first, second]
    assert updated is not None
    assert updated.last_message_preview == second.content

