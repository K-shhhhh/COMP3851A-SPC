from dataclasses import dataclass


@dataclass(slots=True)
class KnowledgeNode:
    """Represents a node in the knowledge graph."""

    id: int
    title: str
    topic: str
    description: str