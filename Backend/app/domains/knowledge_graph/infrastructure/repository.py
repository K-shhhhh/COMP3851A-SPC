"""PostgreSQL knowledge-graph adapter integration boundary.

The database developer implements this class against the migrated
attachment-scoped graph tables. Local tests use ``memory_repository.py`` until
that implementation is complete.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.knowledge_graph.domain.models import (
    KnowledgeEdge,
    KnowledgeNode,
)
from app.domains.knowledge_graph.domain.repository import (
    KnowledgeGraphRepository,
)


class PostgreSQLKnowledgeGraphRepository(
    KnowledgeGraphRepository
):
    """Declare the PostgreSQL adapter expected from the database layer."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind future graph operations to the worker's database session."""

        self._session = session

    async def get_graph_for_attachment(
        self,
        attachment_id: int,
    ) -> tuple[list[KnowledgeNode], list[KnowledgeEdge]]:
        raise NotImplementedError(
            "The attachment-scoped PostgreSQL graph reader is not implemented."
        )

    async def replace_graph_for_attachment(
        self,
        *,
        attachment_id: int,
        nodes: list[KnowledgeNode],
        edges: list[KnowledgeEdge],
    ) -> None:
        raise NotImplementedError(
            "The attachment-scoped PostgreSQL graph writer is not implemented."
        )
