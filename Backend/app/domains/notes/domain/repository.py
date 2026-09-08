# Notes repository contract used by the application service.
# The database developer implements these operations; abstract methods provide no storage.
from abc import ABC, abstractmethod

from app.domains.notes.domain.models import Note


class NoteRepository(ABC):

    @abstractmethod
    async def get_all_notes(self) -> list[Note]:
        raise NotImplementedError

    @abstractmethod
    async def get_note_by_id(
        self,
        note_id: int,
    ) -> Note:
        raise NotImplementedError

    @abstractmethod
    async def create_note(
        self,
        title: str,
        content: str,
        owner_id: int,
    ) -> Note:
        raise NotImplementedError

    @abstractmethod
    async def update_note(
        self,
        note: Note,
    ) -> Note:
        raise NotImplementedError

    @abstractmethod
    async def delete_note(
        self,
        note_id: int,
    ) -> None:
        raise NotImplementedError
