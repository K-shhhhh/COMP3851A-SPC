"""Redis-backed personal chat repository.

Same reasoning as every other Redis repository tonight: InMemoryChatRepository
stores chats and messages in plain Python dicts, wiped on every backend
restart. This implements the exact same ChatRepository interface, backed by
Redis, so conversations and their message history survive restarts and stay
linked to the same user identity (now that auth also survives restarts).

Throwaway once the real PostgreSQL repository lands.
"""

import json
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

from redis.asyncio import Redis

from app.domains.chats.domain.models import (
    ChatMessage,
    ChatMessageRole,
    ChatMessageStatus,
    ChatSource,
    PersonalChat,
)
from app.domains.chats.domain.repository import ChatRepository


class RedisChatRepository(ChatRepository):
    """Store personal chats and their messages in Redis instead of process memory."""

    def __init__(
        self,
        redis_client: Redis,
        *,
        key_prefix: str = "spc:chats:",
    ) -> None:
        self._redis = redis_client
        self._key_prefix = key_prefix

    def _chat_key(self, chat_id: str) -> str:
        return f"{self._key_prefix}chat:{chat_id}"

    def _owner_index_key(self, owner_id: str) -> str:
        return f"{self._key_prefix}by_owner:{owner_id}"

    def _messages_key(self, chat_id: str) -> str:
        return f"{self._key_prefix}messages:{chat_id}"

    def _next_message_id_key(self) -> str:
        return f"{self._key_prefix}next_message_id"

    # ---- serialization -----------------------------------------------

    def _serialize_chat(self, chat: PersonalChat) -> str:
        data = {
            "chat_id": chat.chat_id,
            "owner_id": chat.owner_id,
            "title": chat.title,
            "created_at": chat.created_at.isoformat(),
            "updated_at": chat.updated_at.isoformat(),
            "last_message_preview": chat.last_message_preview,
        }
        if chat.deleted_at is not None:
            data["deleted_at"] = chat.deleted_at.isoformat()
        else:
            data["deleted_at"] = None
        return json.dumps(data)

    def _deserialize_chat(self, raw: str) -> PersonalChat:
        data = json.loads(raw)
        deleted_at = None
        if data["deleted_at"] is not None:
            deleted_at = datetime.fromisoformat(data["deleted_at"])
        return PersonalChat(
            chat_id=data["chat_id"],
            owner_id=data["owner_id"],
            title=data["title"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            last_message_preview=data["last_message_preview"],
            deleted_at=deleted_at,
        )

    def _serialize_message(self, message: ChatMessage) -> str:
        sources_data = []
        for source in message.sources:
            sources_data.append({
                "note_id": source.note_id,
                "note_title": source.note_title,
                "chunk_id": source.chunk_id,
                "page": source.page,
            })

        data = {
            "message_id": message.message_id,
            "chat_id": message.chat_id,
            "role": message.role.value,
            "content": message.content,
            "status": message.status.value,
            "created_at": message.created_at.isoformat(),
            "sources": sources_data,
        }
        return json.dumps(data)

    def _deserialize_message(self, raw: str) -> ChatMessage:
        data = json.loads(raw)

        sources = []
        for source_data in data["sources"]:
            sources.append(ChatSource(
                note_id=source_data["note_id"],
                note_title=source_data["note_title"],
                chunk_id=source_data["chunk_id"],
                page=source_data["page"],
            ))

        return ChatMessage(
            message_id=data["message_id"],
            chat_id=data["chat_id"],
            role=ChatMessageRole(data["role"]),
            content=data["content"],
            status=ChatMessageStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            sources=tuple(sources),
        )

    # ---- interface methods --------------------------------------------

    async def create_chat(self, *, owner_id: str, title: str) -> PersonalChat:
        """Create a new UUID-addressed personal conversation."""

        now = datetime.now(timezone.utc)

        chat = PersonalChat(
            chat_id=str(uuid4()),
            owner_id=owner_id,
            title=title,
            created_at=now,
            updated_at=now,
        )

        await self._redis.set(self._chat_key(chat.chat_id), self._serialize_chat(chat))
        await self._redis.sadd(self._owner_index_key(owner_id), chat.chat_id)

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

        chat_ids = await self._redis.smembers(self._owner_index_key(owner_id))

        matching_chats = []
        for chat_id in chat_ids:
            raw = await self._redis.get(self._chat_key(chat_id))
            if raw is None:
                continue
            chat = self._deserialize_chat(raw)
            if chat.owner_id == owner_id and chat.deleted_at is None:
                matching_chats.append(chat)

        matching_chats.sort(key=lambda item: item.updated_at, reverse=True)

        total = len(matching_chats)
        page = matching_chats[offset : offset + limit]

        return page, total

    async def get_owned_chat(
        self,
        *,
        chat_id: str,
        owner_id: str,
    ) -> PersonalChat | None:
        """Return an active chat only to its owner."""

        raw = await self._redis.get(self._chat_key(chat_id))

        if raw is None:
            return None

        chat = self._deserialize_chat(raw)

        if chat.deleted_at is not None:
            return None

        if chat.owner_id != owner_id:
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

        chat = await self.get_owned_chat(chat_id=chat_id, owner_id=owner_id)

        if chat is None:
            return None

        updated = replace(
            chat,
            title=title,
            updated_at=datetime.now(timezone.utc),
        )

        await self._redis.set(self._chat_key(chat_id), self._serialize_chat(updated))

        return updated

    async def soft_delete_owned_chat(
        self,
        *,
        chat_id: str,
        owner_id: str,
        deleted_at: datetime,
    ) -> bool:
        """Soft-delete a chat only when the owner matches."""

        chat = await self.get_owned_chat(chat_id=chat_id, owner_id=owner_id)

        if chat is None:
            return False

        updated = replace(
            chat,
            deleted_at=deleted_at,
            updated_at=deleted_at,
        )

        await self._redis.set(self._chat_key(chat_id), self._serialize_chat(updated))

        return True

    async def create_message(
        self,
        *,
        chat_id: str,
        role: ChatMessageRole,
        content: str,
        sources: tuple[ChatSource, ...] = (),
    ) -> ChatMessage:
        """Persist a completed message and update the chat preview.

        NOTE: like the other Redis repositories tonight, updating the chat's
        own preview/timestamp is a read-modify-write, not an atomic
        transaction. Fine for solo/demo use; a real MULTI/WATCH transaction
        would be needed before genuine concurrent multi-user traffic.
        """

        raw_chat = await self._redis.get(self._chat_key(chat_id))

        if raw_chat is None:
            raise ValueError("cannot add a message to a missing chat")

        chat = self._deserialize_chat(raw_chat)

        if chat.deleted_at is not None:
            raise ValueError("cannot add a message to a missing chat")

        # A single counter shared across every chat, matching the in-memory
        # adapter's own itertools.count(start=1) -- message_id is globally
        # unique, not just unique within one chat.
        new_message_id = await self._redis.incr(self._next_message_id_key())

        now = datetime.now(timezone.utc)

        message = ChatMessage(
            message_id=new_message_id,
            chat_id=chat_id,
            role=role,
            content=content,
            status=ChatMessageStatus.COMPLETED,
            created_at=now,
            sources=sources,
        )

        await self._redis.rpush(self._messages_key(chat_id), self._serialize_message(message))

        updated_chat = replace(
            chat,
            updated_at=now,
            last_message_preview=content[:120],
        )
        await self._redis.set(self._chat_key(chat_id), self._serialize_chat(updated_chat))

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

        raw_chat = await self._redis.get(self._chat_key(chat_id))

        if raw_chat is None:
            return [], 0

        chat = self._deserialize_chat(raw_chat)

        if chat.deleted_at is not None:
            return [], 0

        total = await self._redis.llen(self._messages_key(chat_id))

        # LRANGE's end index is inclusive, so offset+limit-1, not offset+limit.
        raw_messages = await self._redis.lrange(
            self._messages_key(chat_id), offset, offset + limit - 1
        )

        messages = []
        for raw_message in raw_messages:
            messages.append(self._deserialize_message(raw_message))

        return messages, total
