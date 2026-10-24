"""Shared input validation for PostgreSQL cosine searches."""

from math import isfinite

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

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


async def enable_filtered_vector_search(session: AsyncSession) -> None:
    """Make the vector index keep looking until it finds enough of THIS user's chunks.

    The HNSW index picks its nearest candidates across every student's chunks
    and only then applies the "belongs to this user" filter. On a database with
    many users that can leave nothing, so the chat wrongly says the student has
    no processed notes. Iterative scan tells the index to keep scanning until
    the filter has produced enough rows. The setting lasts for this transaction
    only. If the database does not support it (pgvector older than 0.8), the
    search carries on as before.
    """

    try:
        async with session.begin_nested():
            await session.execute(
                text("SET LOCAL hnsw.iterative_scan = strict_order")
            )
    except Exception:
        return
