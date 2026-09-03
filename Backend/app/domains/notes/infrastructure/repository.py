# DEMO notes repository: returns constructed objects instead of executing SQL.
# Do not interpret successful responses as persisted data or authenticated access.
from app.domains.notes.domain.models import Note
from app.domains.notes.domain.repository import NoteRepository


class PostgreSQLNoteRepository(NoteRepository):

    async def get_all_notes(self) -> list[Note]:

        return [
            Note(
                id=1,
                title="Introduction to AI",
                content="This is a placeholder note.",
                owner_id=1,
            )
        ]

    async def get_note_by_id(
        self,
        note_id: int,
    ) -> Note:

        return Note(
            id=note_id,
            title="Introduction to AI",
            content="This is a placeholder note.",
            owner_id=1,
        )

    async def create_note(
        self,
        title: str,
        content: str,
        owner_id: int,
    ) -> Note:

        return Note(
            id=2,
            title=title,
            content=content,
            owner_id=owner_id,
        )

    async def update_note(
        self,
        note: Note,
    ) -> Note:

        return note

    async def delete_note(
        self,
        note_id: int,
    ) -> None:

        return None
