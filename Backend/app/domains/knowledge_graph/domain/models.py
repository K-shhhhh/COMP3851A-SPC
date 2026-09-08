# Knowledge Graph domain data objects, independent of FastAPI and database libraries.
# These dataclasses are not database tables or migrations.
from dataclasses import dataclass


@dataclass(slots=True)
class KnowledgeNode:
    """Represents a node in the knowledge graph."""

    id: int
    title: str
    topic: str
    description: str
