# Public notes request/response shapes used by FastAPI validation and OpenAPI.
# Coordinate field-name changes with the frontend; schemas alone do not enforce permissions.
from pydantic import BaseModel


class NoteResponse(BaseModel):
    id: int
    title: str
    content: str
    owner_id: int


class CreateNoteRequest(BaseModel):
    title: str
    content: str
    owner_id: int


class UpdateNoteRequest(BaseModel):
    title: str
    content: str
    owner_id: int
