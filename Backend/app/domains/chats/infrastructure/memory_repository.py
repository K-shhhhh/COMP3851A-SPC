"""Temporary in-memory personal-chat repository for local development."""

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from itertools import count
from uuid import uuid4

from app.domains.chats.domain.models import (
    ChatMessage,
    ChatMessageRole,
    ChatMessageStatus,
    ChatSource,
    PersonalChat,
)
from app.domains.chats.domain.repository import ChatRepository


class InMemoryChatRepository(ChatRepository):
    """Store chats and messages in one backend process for local testing."""

    def __init__(self) -> None:
        """Initialize empty stores and a database-style message sequence."""

        self._chats: dict[str, PersonalChat] = {}
        self._messages: dict[str, list[ChatMessage]] = {}
        self._message_ids = count(start=1)
        self._lock = asyncio.Lock()

    async def create_chat(self, *, owner_id: str, title: str) -> PersonalChat:
        """Create a new UUID-addressed personal conversation."""

        async with self._lock:
            now = datetime.now(timezone.utc)
            chat = PersonalChat(
                chat_id=str(uuid4()),
                owner_id=owner_id,
                title=title,
                created_at=now,
                updated_at=now,
            )
            self._chats[chat.chat_id] = chat
            self._messages[chat.chat_id] = []
            return chat

    async def list_owned_chats(
        self,
        *,
        owner_id: str,
        offset: int,
        limit: int,
    ) -> tuple[list[PersonalChat], int]:
        """Return newest-active chats for one owner."""

        if offset < 0 or limit <= 0:
            raise ValueError("invalid pagination")

        async with self._lock:
            chats = [
                chat
                for chat in self._chats.values()
                if chat.owner_id == owner_id and chat.deleted_at is None
            ]
            chats.sort(key=lambda item: item.updated_at, reverse=True)
            return chats[offset : offset + limit], len(chats)

    async def get_owned_chat(
        self,
        *,
        chat_id: str,
        owner_id: str,
    ) -> PersonalChat | None:
        """Return an active chat only to its owner."""

        async with self._lock:
            chat = self._chats.get(chat_id)
            if (
                chat is None
                or chat.deleted_at is not None
                or chat.owner_id != owner_id
            ):
                return None
            return chat

    async def rename_owned_chat(
        self,
        *,
        chat_id: str,
        owner_id: str,
        title: str,
    ) -> PersonalChat | None:
        """Rename an active chat only when the owner matches."""

        async with self._lock:
            chat = self._chats.get(chat_id)
            if (
                chat is None
                or chat.deleted_at is not None
                or chat.owner_id != owner_id
            ):
                return None

            updated = replace(
                chat,
                title=title,
                updated_at=datetime.now(timezone.utc),
            )
            self._chats[chat_id] = updated
            return updated

    async def soft_delete_owned_chat(
        self,
        *,
        chat_id: str,
        owner_id: str,
        deleted_at: datetime,
    ) -> bool:
        """Soft-delete a chat only when the owner matches."""

        async with self._lock:
            chat = self._chats.get(chat_id)
            if (
                chat is None
                or chat.deleted_at is not None
                or chat.owner_id != owner_id
            ):
                return False

            self._chats[chat_id] = replace(
                chat,
                deleted_at=deleted_at,
                updated_at=deleted_at,
            )
            return True

    async def create_message(
        self,
        *,
        chat_id: str,
        role: ChatMessageRole,
        content: str,
        sources: tuple[ChatSource, ...] = (),
    ) -> ChatMessage:
        """Persist a completed message and update the chat preview."""

        async with self._lock:
            chat = self._chats.get(chat_id)
            if chat is None or chat.deleted_at is not None:
                raise ValueError("cannot add a message to a missing chat")

            now = datetime.now(timezone.utc)
            message = ChatMessage(
                message_id=next(self._message_ids),
                chat_id=chat_id,
                role=role,
                content=content,
                status=ChatMessageStatus.COMPLETED,
                created_at=now,
                sources=sources,
            )
            self._messages[chat_id].append(message)
            self._chats[chat_id] = replace(
                chat,
                updated_at=now,
                last_message_preview=content[:120],
            )
            return message

    async def list_messages(
        self,
        *,
        chat_id: str,
        offset: int,
        limit: int,
    ) -> tuple[list[ChatMessage], int]:
        """Return a stable oldest-first page of active-chat messages."""

        if offset < 0 or limit <= 0:
            raise ValueError("invalid pagination")

        async with self._lock:
            chat = self._chats.get(chat_id)
            if chat is None or chat.deleted_at is not None:
                return [], 0

            messages = list(self._messages.get(chat_id, ()))
            return messages[offset : offset + limit], len(messages)

