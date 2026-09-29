# Knowledge Graph domain data objects, independent of FastAPI and database libraries.
# These dataclasses are not database tables or migrations.
from dataclasses import dataclass


@dataclass(slots=True)
class KnowledgeNode:
    """One concept extracted from an attachment's study material.

    id is a real database id once read back from storage, but a temporary,
    batch-local id when freshly produced by graph_generation.py -- see
    that module's docstring for the id-resolution convention.
    """

    id: int
    attachment_id: int
    title: str
    topic: str
    description: str
    source_chunk_id: int | None


@dataclass(slots=True)
class KnowledgeEdge:
    """One relationship between two nodes within the same attachment's graph."""

    id: int
    attachment_id: int
    source_node_id: int
    target_node_id: int
    label: str | None
