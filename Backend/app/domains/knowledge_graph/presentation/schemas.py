"""Public response models for attachment-scoped knowledge graphs."""

from pydantic import BaseModel

from app.domains.knowledge_graph.domain.models import (
    KnowledgeEdge,
    KnowledgeNode,
)


class KnowledgeNodeResponse(BaseModel):
    """Public concept node with an optional source citation."""

    id: int
    attachment_id: int
    title: str
    topic: str
    description: str
    source_chunk_id: int | None

    @classmethod
    def from_node(cls, node: KnowledgeNode) -> "KnowledgeNodeResponse":
        """Convert a domain node into its public representation."""

        return cls(
            id=node.id,
            attachment_id=node.attachment_id,
            title=node.title,
            topic=node.topic,
            description=node.description,
            source_chunk_id=node.source_chunk_id,
        )


class KnowledgeEdgeResponse(BaseModel):
    """Public directed relationship between two graph nodes."""

    id: int
    attachment_id: int
    source_node_id: int
    target_node_id: int
    label: str | None

    @classmethod
    def from_edge(cls, edge: KnowledgeEdge) -> "KnowledgeEdgeResponse":
        """Convert a domain edge into its public representation."""

        return cls(
            id=edge.id,
            attachment_id=edge.attachment_id,
            source_node_id=edge.source_node_id,
            target_node_id=edge.target_node_id,
            label=edge.label,
        )


class KnowledgeGraphResponse(BaseModel):
    """Complete visualization payload for one uploaded document."""

    attachment_id: int
    nodes: list[KnowledgeNodeResponse]
    edges: list[KnowledgeEdgeResponse]

    @classmethod
    def from_graph(
        cls,
        *,
        attachment_id: int,
        nodes: list[KnowledgeNode],
        edges: list[KnowledgeEdge],
    ) -> "KnowledgeGraphResponse":
        """Convert domain graph objects into one frontend payload."""

        return cls(
            attachment_id=attachment_id,
            nodes=[KnowledgeNodeResponse.from_node(node) for node in nodes],
            edges=[KnowledgeEdgeResponse.from_edge(edge) for edge in edges],
        )
