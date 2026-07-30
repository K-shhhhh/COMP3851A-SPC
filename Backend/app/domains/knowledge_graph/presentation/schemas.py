from pydantic import BaseModel


class KnowledgeNodeResponse(BaseModel):
    id: int
    title: str
    topic: str
    description: str