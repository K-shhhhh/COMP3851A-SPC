"""Authorized ready-note chunk retrieval boundary for personal chat."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.domains.chats.domain.models import ChatSource


@dataclass(frozen=True, slots=True)
class GroundingChunk:
    """One ready and authorized chunk supplied to the RAG answer adapter."""

    content: str
    source: ChatSource

    def __post_init__(self) -> None:
        """Reject empty retrieved context."""

        if not self.content.strip():
            raise ValueError("grounding chunk content must not be empty")


class ReadyNoteChunkRepository(ABC):
    """Load only ready chunks the authenticated student may use."""

    @abstractmethod
    async def list_ready_chunks_for_user(
        self,
        *,
        user_id: str,
    ) -> tuple[GroundingChunk, ...]:
        """Return non-deleted ready-note chunks scoped to one student."""

        raise NotImplementedError

    @abstractmethod
    async def search_ready_chunks_for_user(
        self,
        *,
        user_id: str,
        query_embedding: tuple[float, ...],
        limit: int,
    ) -> tuple[GroundingChunk, ...]:
        """Return top-ranked ready library chunks owned by one student.

        All My Notes attachments are treated equally in this prototype. The
        database adapter applies ownership/status/deletion filters before
        ordering by pgvector cosine distance and applying ``limit``.
        """

        raise NotImplementedError
