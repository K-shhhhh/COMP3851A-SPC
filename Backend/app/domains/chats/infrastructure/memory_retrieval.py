"""Seedable local ready-note chunks used by Chat service tests."""

import asyncio

from app.domains.chats.domain.retrieval import (
    GroundingChunk,
    ReadyNoteChunkRepository,
)


class InMemoryReadyNoteChunkRepository(ReadyNoteChunkRepository):
    """Keep already-authorized chunks in memory until PostgreSQL is ready."""

    def __init__(self) -> None:
        """Initialize an empty user-to-chunks mapping."""

        self._chunks: dict[str, tuple[GroundingChunk, ...]] = {}
        self._lock = asyncio.Lock()

    async def replace_user_chunks(
        self,
        *,
        user_id: str,
        chunks: tuple[GroundingChunk, ...],
    ) -> None:
        """Seed authorized chunks for isolated local tests and demos."""

        async with self._lock:
            self._chunks[user_id] = chunks

    async def replace_attachment_chunks(
        self,
        *,
        user_id: str,
        note_id: int,
        chunks: tuple[GroundingChunk, ...],
    ) -> None:
        """Replace one uploaded note's chunks without removing other notes.

        This write operation exists only for the temporary local demo
        processor. PostgreSQL/pgvector will replace it with transactional
        chunk persistence and permission-scoped retrieval.
        """

        if any(chunk.source.note_id != note_id for chunk in chunks):
            raise ValueError("all chunks must belong to the supplied note_id")

        async with self._lock:
            existing = self._chunks.get(user_id, ())
            other_notes = tuple(
                chunk
                for chunk in existing
                if chunk.source.note_id != note_id
            )
            self._chunks[user_id] = other_notes + chunks

    async def list_ready_chunks_for_user(
        self,
        *,
        user_id: str,
        note_id: int | None = None,
    ) -> tuple[GroundingChunk, ...]:
        """Return only the chunks previously scoped to this user."""

        async with self._lock:
            chunks = self._chunks.get(user_id, ())
        if note_id is None:
            return chunks
        selected = []
        for chunk in chunks:
            if chunk.source.note_id == note_id:
                selected.append(chunk)
        return tuple(selected)

    async def search_ready_chunks_for_user(
        self,
        *,
        user_id: str,
        query_embedding: tuple[float, ...],
        limit: int,
        note_id: int | None = None,
    ) -> tuple[GroundingChunk, ...]:
        """Provide a deterministic bounded fallback for isolated tests."""

        if limit <= 0:
            raise ValueError("semantic search limit must be positive")
        chunks = await self.list_ready_chunks_for_user(
            user_id=user_id,
            note_id=note_id,
        )
        return chunks[:limit]
