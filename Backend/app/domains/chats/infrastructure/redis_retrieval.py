"""Redis-backed ready-note chunk repository, shared across the backend and
worker processes.

Same reasoning as redis_repository.py for attachments: the Celery worker
runs in a separate container and cannot see the backend's in-process dict,
so chunks published by the worker need to live somewhere the chat endpoint's
process can also read them from. Redis is that somewhere.

Throwaway once the real PostgreSQL/pgvector repository lands.
"""

import json

from redis.asyncio import Redis

from app.domains.chats.domain.models import ChatSource
from app.domains.chats.domain.retrieval import (
    GroundingChunk,
    ReadyNoteChunkRepository,
)


class RedisReadyNoteChunkRepository(ReadyNoteChunkRepository):
    """Store a user's authorized chunks in Redis instead of process memory."""

    def __init__(
        self,
        redis_client: Redis,
        *,
        key_prefix: str = "spc:chats:chunks:",
    ) -> None:
        self._redis = redis_client
        self._key_prefix = key_prefix

    def _user_key(self, user_id: str) -> str:
        return f"{self._key_prefix}{user_id}"

    # ---- serialization -----------------------------------------------
    # GroundingChunk and ChatSource are both frozen dataclasses, so they
    # need converting to plain dicts before they can be stored as JSON.

    def _serialize_chunk(self, chunk: GroundingChunk) -> dict:
        return {
            "content": chunk.content,
            "note_id": chunk.source.note_id,
            "note_title": chunk.source.note_title,
            "chunk_id": chunk.source.chunk_id,
            "page": chunk.source.page,
        }

    def _deserialize_chunk(self, data: dict) -> GroundingChunk:
        source = ChatSource(
            note_id=data["note_id"],
            note_title=data["note_title"],
            chunk_id=data["chunk_id"],
            page=data["page"],
        )
        return GroundingChunk(content=data["content"], source=source)

    # ---- interface methods --------------------------------------------

    async def list_ready_chunks_for_user(
        self,
        *,
        user_id: str,
    ) -> tuple[GroundingChunk, ...]:
        """Return only the chunks previously scoped to this user."""

        raw = await self._redis.get(self._user_key(user_id))

        if raw is None:
            return ()

        stored_items = json.loads(raw)
        chunks = []
        for item in stored_items:
            chunks.append(self._deserialize_chunk(item))

        return tuple(chunks)

    async def replace_attachment_chunks(
        self,
        *,
        user_id: str,
        note_id: int,
        chunks: tuple[GroundingChunk, ...],
    ) -> None:
        """Replace one uploaded note's chunks without removing other notes.

        NOTE: this is a read-modify-write over the network, not an atomic
        Redis transaction. Fine for solo/demo use with one upload at a time;
        two uploads finishing for the same user at the exact same moment
        could race. Worth a proper Redis transaction (WATCH/MULTI) before
        this sees real concurrent multi-user load.
        """

        for chunk in chunks:
            if chunk.source.note_id != note_id:
                raise ValueError("all chunks must belong to the supplied note_id")

        existing = await self.list_ready_chunks_for_user(user_id=user_id)

        other_notes = []
        for chunk in existing:
            if chunk.source.note_id != note_id:
                other_notes.append(chunk)

        combined = tuple(other_notes) + chunks

        serialized_items = []
        for chunk in combined:
            serialized_items.append(self._serialize_chunk(chunk))

        await self._redis.set(self._user_key(user_id), json.dumps(serialized_items))
