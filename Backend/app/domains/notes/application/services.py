# Notes use cases depend on repository interfaces, not HTTP or SQL.
# Current methods delegate to repositories; authorization and business rules still need implementation.
from app.domains.notes.domain.models import Note
from app.domains.notes.domain.repository import NoteRepository


class NoteService:

    def __init__(
        self,
        repository: NoteRepository,
    ):
        self.repository = repository

    async def get_all_notes(self):

        return await self.repository.get_all_notes()

    async def get_note_by_id(
        self,
        note_id: int,
    ):

        return await self.repository.get_note_by_id(note_id)

    async def create_note(
        self,
        title: str,
        content: str,
        owner_id: int,
    ):

        return await self.repository.create_note(
            title,
            content,
            owner_id,
        )

    async def update_note(
        self,
        note: Note,
    ):

        return await self.repository.update_note(note)

    async def delete_note(
        self,
        note_id: int,
    ):

        await self.repository.delete_note(note_id)
