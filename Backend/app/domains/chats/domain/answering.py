"""Boundary between the Chat use case and Krish's synchronous RAG pipeline."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.domains.chats.domain.models import ChatSource
from app.domains.chats.domain.retrieval import GroundingChunk


@dataclass(frozen=True, slots=True)
class GeneratedAnswer:
    """Provider-neutral answer returned by a synchronous RAG adapter."""

    content: str
    sources: tuple[ChatSource, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Ensure the adapter returned displayable answer content."""

        if not self.content.strip():
            raise ValueError("generated answer content must not be empty")


class ChatAnswerGenerator(ABC):
    """Generate one grounded response without exposing RAG implementation."""

    @abstractmethod
    async def answer_question(
        self,
        *,
        question: str,
        chunks: tuple[GroundingChunk, ...],
    ) -> GeneratedAnswer:
        """Return an answer grounded only in the supplied authorized chunks."""

        raise NotImplementedError

