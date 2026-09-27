"""Ready-chunk retrieval boundary for Study Group companion messages."""

from abc import ABC, abstractmethod

from app.domains.chats.domain.retrieval import GroundingChunk


class StudyGroupReadyChunkRepository(ABC):
    """Load only ready chunks authorized for one exact group channel."""

    @abstractmethod
    async def list_ready_chunks_for_channel(
        self,
        *,
        group_id: str,
        channel_id: str,
    ) -> tuple[GroundingChunk, ...]:
        """Return non-deleted ready chunks scoped to group and channel."""

        raise NotImplementedError
