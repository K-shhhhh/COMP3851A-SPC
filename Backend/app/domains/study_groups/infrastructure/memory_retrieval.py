"""Seedable group/channel chunk retrieval for tests and local development."""

import asyncio

from app.domains.chats.domain.retrieval import GroundingChunk
from app.domains.study_groups.domain.retrieval import (
    StudyGroupReadyChunkRepository,
)


class InMemoryStudyGroupReadyChunkRepository(
    StudyGroupReadyChunkRepository
):
    """Keep already-authorized chunks isolated by group and channel."""

    def __init__(self) -> None:
        """Initialize an empty group/channel-to-chunks mapping."""

        self._chunks: dict[
            tuple[str, str],
            tuple[GroundingChunk, ...],
        ] = {}
        self._lock = asyncio.Lock()

    async def replace_channel_chunks(
        self,
        *,
        group_id: str,
        channel_id: str,
        chunks: tuple[GroundingChunk, ...],
    ) -> None:
        """Seed ready chunks for one exact channel without cross-group reuse."""

        async with self._lock:
            self._chunks[(group_id, channel_id)] = chunks

    async def list_ready_chunks_for_channel(
        self,
        *,
        group_id: str,
        channel_id: str,
    ) -> tuple[GroundingChunk, ...]:
        """Return only chunks previously scoped to this group channel."""

        async with self._lock:
            return self._chunks.get((group_id, channel_id), ())
