"""Nomic question-embedding adapter for semantic chunk retrieval."""

import asyncio

from app.ai.rag.embedding import embed_text
from app.domains.chats.domain.embedding import (
    QUESTION_EMBEDDING_DIMENSIONS,
    QuestionEmbeddingProvider,
)


class NomicQuestionEmbeddingProvider(QuestionEmbeddingProvider):
    """Run Krish's synchronous Nomic embedding call outside the event loop."""

    async def embed_question(self, question: str) -> tuple[float, ...]:
        """Embed one validated question and enforce the pgvector dimension."""

        embedding = tuple(await asyncio.to_thread(embed_text, question))
        if len(embedding) != QUESTION_EMBEDDING_DIMENSIONS:
            raise ValueError(
                "question embedding must contain exactly "
                f"{QUESTION_EMBEDDING_DIMENSIONS} values"
            )
        return embedding
