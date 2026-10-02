"""Provider-neutral boundary for embedding one user question."""

from abc import ABC, abstractmethod


QUESTION_EMBEDDING_DIMENSIONS = 768


class QuestionEmbeddingProvider(ABC):
    """Create the query vector used by authorized semantic retrieval."""

    @abstractmethod
    async def embed_question(self, question: str) -> tuple[float, ...]:
        """Return one normalized 768-dimensional question embedding."""

        raise NotImplementedError
