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