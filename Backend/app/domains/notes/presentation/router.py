from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import get_note_service
from app.domains.notes.application.services import NoteService
from app.domains.notes.domain.models import Note
from app.domains.notes.presentation.schemas import (
    CreateNoteRequest,
    NoteResponse,
    UpdateNoteRequest,
)

router = APIRouter(
    prefix="/notes",
    tags=["Notes"],
)


@router.get(
    "/",
    response_model=list[NoteResponse],
)
async def get_all_notes(
    service: NoteService = Depends(get_note_service),
):
    return await service.get_all_notes()


@router.get(
    "/{note_id}",
    response_model=NoteResponse,
)
async def get_note_by_id(
    note_id: int,
    service: NoteService = Depends(get_note_service),
):
    return await service.get_note_by_id(note_id)


@router.post(
    "/",
    response_model=NoteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_note(
    request: CreateNoteRequest,
    service: NoteService = Depends(get_note_service),
):
    return await service.create_note(
        request.title,
        request.content,
        request.owner_id,
    )


@router.put(
    "/{note_id}",
    response_model=NoteResponse,
)
async def update_note(
    note_id: int,
    request: UpdateNoteRequest,
    service: NoteService = Depends(get_note_service),
):

    note = Note(
        id=note_id,
        title=request.title,
        content=request.content,
        owner_id=request.owner_id,
    )

    return await service.update_note(note)


@router.delete(
    "/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_note(
    note_id: int,
    service: NoteService = Depends(get_note_service),
):

    await service.delete_note(note_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)