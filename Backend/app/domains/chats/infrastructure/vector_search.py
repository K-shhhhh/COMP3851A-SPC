"""Shared input validation for PostgreSQL cosine searches."""

from math import isfinite

from app.domains.chats.domain.embedding import QUESTION_EMBEDDING_DIMENSIONS

SEMANTIC_EMBEDDING_MODEL_VERSION = "nomic-embed-text"

def validate_semantic_search(
    query_embedding: tuple[float, ...], limit: int,
) -> list[float]:
    """Return a valid pgvector query without silently accepting invalid limits."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise ValueError("semantic search limit must be a positive integer")
    if len(query_embedding) != QUESTION_EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"question embedding must contain exactly {QUESTION_EMBEDDING_DIMENSIONS} values"
        )
    try:
        embedding = [float(value) for value in query_embedding]
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("question embedding must contain finite numbers") from exc
    if not all(isfinite(value) for value in embedding):
        raise ValueError("question embedding must contain finite numbers")
    if not any(embedding):
        raise ValueError("question embedding must be nonzero for cosine distance")
    return embedding
