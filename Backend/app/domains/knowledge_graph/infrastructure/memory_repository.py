"""Process-local knowledge-graph repository for tests and local integration."""

import asyncio

from app.domains.knowledge_graph.domain.models import (
    KnowledgeEdge,
    KnowledgeNode,
)
from app.domains.knowledge_graph.domain.repository import (
    KnowledgeGraphRepository,
)


class InMemoryKnowledgeGraphRepository(KnowledgeGraphRepository):
    """Store complete attachment graphs until the process restarts."""

    def __init__(self) -> None:
        self._graphs: dict[
            int,
            tuple[list[KnowledgeNode], list[KnowledgeEdge]],
        ] = {}
        self._lock = asyncio.Lock()

    async def get_graph_for_attachment(
        self,
        attachment_id: int,
    ) -> tuple[list[KnowledgeNode], list[KnowledgeEdge]]:
        """Return defensive copies of one attachment's graph."""

        async with self._lock:
            nodes, edges = self._graphs.get(attachment_id, ([], []))
            return list(nodes), list(edges)

    async def replace_graph_for_attachment(
        self,
        *,
        attachment_id: int,
        nodes: list[KnowledgeNode],
        edges: list[KnowledgeEdge],
    ) -> None:
        """Replace one attachment's graph as a single locked operation."""

        async with self._lock:
            self._graphs[attachment_id] = (list(nodes), list(edges))
