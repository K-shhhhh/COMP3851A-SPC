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
        response_format: str | None = None,
        mode: str | None = None,
    ) -> GeneratedAnswer:
        """Return an answer grounded only in the supplied authorized chunks.

        response_format is one of "paragraph", "bullet_points", "table", or
        None (defaults to paragraph).

        mode is one of "default", "summarizer", "quiz", "facilitator", or
        None (defaults to "default"/Companion). Personal chat never needs to
        set this explicitly; group chat's @-mention picker is the intended
        caller for the other three.

        Implementations that don't support formatting or modes yet should
        still accept and ignore these, rather than omitting the parameters
        -- callers pass them as keyword arguments.
        """

        raise NotImplementedError

