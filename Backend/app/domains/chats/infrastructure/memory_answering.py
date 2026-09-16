"""Deterministic local answer adapter used before Krish's RAG merge."""

from app.domains.chats.domain.answering import (
    ChatAnswerGenerator,
    GeneratedAnswer,
)
from app.domains.chats.domain.retrieval import GroundingChunk


class LocalGroundedAnswerGenerator(ChatAnswerGenerator):
    """Return a transparent local answer without pretending to be the AI model."""

    async def answer_question(
        self,
        *,
        question: str,
        chunks: tuple[GroundingChunk, ...],
    ) -> GeneratedAnswer:
        """Build a predictable response for endpoint and contract testing."""

        del question
        first = chunks[0]
        return GeneratedAnswer(
            content=f"Based on {first.source.note_title}: {first.content}",
            sources=(first.source,),
        )

