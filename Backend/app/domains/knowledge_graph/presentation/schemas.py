# Public knowledge graph request/response shapes used by FastAPI validation and OpenAPI.
# Coordinate field-name changes with the frontend; schemas alone do not enforce permissions.
from pydantic import BaseModel


class KnowledgeNodeResponse(BaseModel):
    id: int
    title: str
    topic: str
    description: str
