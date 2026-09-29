"""Attachment-scoped knowledge-graph domain models.

These objects contain no FastAPI, SQLAlchemy, or model-provider details. One
uploaded attachment owns one graph; nodes may cite the document chunk from
which the concept was derived.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KnowledgeNode:
    """Represent one persisted concept in an attachment's graph."""

    id: int
    attachment_id: int
    title: str
    topic: str
    description: str
    source_chunk_id: int | None = None


@dataclass(frozen=True, slots=True)
class KnowledgeEdge:
    """Represent one directed relationship between two graph nodes."""

    id: int
    attachment_id: int
    source_node_id: int
    target_node_id: int
    label: str | None = None
