"""Persistence contract for attachment-scoped knowledge graphs."""

from abc import ABC, abstractmethod

from app.domains.knowledge_graph.domain.models import (
    KnowledgeEdge,
    KnowledgeNode,
)


class KnowledgeGraphRepository(ABC):
    """Define storage operations implemented by infrastructure adapters."""

    @abstractmethod
    async def get_graph_for_attachment(
        self,
        attachment_id: int,
    ) -> tuple[list[KnowledgeNode], list[KnowledgeEdge]]:
        """Return the nodes and edges stored for one attachment."""

        raise NotImplementedError

    @abstractmethod
    async def replace_graph_for_attachment(
        self,
        *,
        attachment_id: int,
        nodes: list[KnowledgeNode],
        edges: list[KnowledgeEdge],
    ) -> None:
        """Atomically replace the complete graph for one attachment.

        Node identifiers supplied by the generator are graph-local references.
        A database adapter must map them to generated database identifiers
        before inserting edges, and must complete the replacement in one
        transaction.
        """

        raise NotImplementedError
