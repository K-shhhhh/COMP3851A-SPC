"""Authenticated HTTP endpoints for the student's Notes Library."""

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    Response,
    UploadFile,
    status,
)

from app.api.dependencies import get_current_user, get_note_service
from app.api.error_handlers import ApiError
from app.core.config import settings
from app.domains.auth.domain.models import User
from app.domains.notes.application.services import NoteService
from app.domains.notes.domain.exceptions import (
    AttachmentNotFoundError,
    AttachmentStorageError,
    EmptyFileError,
    FileTooLargeError,
    InvalidPdfError,
    ProcessingDispatchError,
    UnsafeFilenameError,
    UnsupportedFileTypeError,
)
from app.domains.notes.domain.models import NoteProcessingStatus
from app.domains.notes.presentation.schemas import (
    NoteListItemResponse,
    NoteListResponse,
    NoteResponse,
    NoteStatusResponse,
)

router = APIRouter(
    prefix="/notes",
    tags=["Notes"],
)


@router.post(
    "/upload",
    response_model=NoteResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_note(
    file: UploadFile = File(...),
    title: str | None = Form(default=None, max_length=150),
    current_user: User = Depends(get_current_user),
    service: NoteService = Depends(get_note_service),
) -> NoteResponse:
    """Accept a private PDF and queue it for document processing."""

    try:
        # Read at most one byte beyond the limit so oversized uploads can be
        # rejected without loading an unbounded request into memory.
        data = await file.read(settings.MAX_NOTE_UPLOAD_SIZE_BYTES + 1)
        attachment = await service.upload_note(
            user_id=current_user.id,
            original_filename=file.filename,
            content_type=file.content_type,
            data=data,
            title=title,
        )
    except Exception as exc:
        _raise_note_api_error(exc)
        raise
    finally:
        await file.close()

    return NoteResponse.from_attachment(attachment)


@router.get(
    "",
    response_model=NoteListResponse,
)
async def list_notes(
    processing_status: NoteProcessingStatus | None = Query(
        default=None,
        alias="status",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: NoteService = Depends(get_note_service),
) -> NoteListResponse:
    """List the authenticated student's non-deleted My Notes uploads."""

    items, total = await service.list_notes(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        processing_status=processing_status,
    )

    return NoteListResponse(
        items=[
            NoteListItemResponse.from_attachment(item)
            for item in items
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get(
    "/{note_id}",
    response_model=NoteResponse,
)
async def get_note(
    note_id: int,
    current_user: User = Depends(get_current_user),
    service: NoteService = Depends(get_note_service),
) -> NoteResponse:
    """Return metadata for one owned Notes Library attachment."""

    try:
        attachment = await service.get_note(
            attachment_id=note_id,
            user_id=current_user.id,
        )
    except Exception as exc:
        _raise_note_api_error(exc)
        raise

    return NoteResponse.from_attachment(attachment)


@router.get(
    "/{note_id}/status",
    response_model=NoteStatusResponse,
)
async def get_note_status(
    note_id: int,
    current_user: User = Depends(get_current_user),
    service: NoteService = Depends(get_note_service),
) -> NoteStatusResponse:
    """Return processing progress for one owned Notes Library upload."""

    try:
        attachment = await service.get_note(
            attachment_id=note_id,
            user_id=current_user.id,
        )
    except Exception as exc:
        _raise_note_api_error(exc)
        raise

    return NoteStatusResponse.from_attachment(attachment)


@router.delete(
    "/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_note(
    note_id: int,
    current_user: User = Depends(get_current_user),
    service: NoteService = Depends(get_note_service),
) -> Response:
    """Delete one owned Notes Library attachment."""

    try:
        await service.delete_note(
            attachment_id=note_id,
            user_id=current_user.id,
        )
    except Exception as exc:
        _raise_note_api_error(exc)
        raise

    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _raise_note_api_error(exc: Exception) -> None:
    """Convert expected Notes failures into the shared API error shape."""

    if isinstance(exc, AttachmentNotFoundError):
        raise ApiError(
            status_code=404,
            code="NOTE_NOT_FOUND",
            message="The requested note was not found.",
        ) from exc

    if isinstance(exc, FileTooLargeError):
        raise ApiError(
            status_code=413,
            code="FILE_TOO_LARGE",
            message=str(exc),
            details={
                "maximum_size_bytes": exc.maximum_size_bytes,
            },
        ) from exc

    if isinstance(exc, UnsupportedFileTypeError):
        raise ApiError(
            status_code=415,
            code="UNSUPPORTED_FILE_TYPE",
            message=str(exc),
        ) from exc

    if isinstance(exc, EmptyFileError):
        raise ApiError(
            status_code=422,
            code="EMPTY_FILE",
            message=str(exc),
        ) from exc

    if isinstance(exc, InvalidPdfError):
        raise ApiError(
            status_code=422,
            code="INVALID_PDF",
            message=str(exc),
        ) from exc

    if isinstance(exc, UnsafeFilenameError):
        raise ApiError(
            status_code=422,
            code="INVALID_FILENAME",
            message=str(exc),
        ) from exc

    if isinstance(exc, AttachmentStorageError):
        raise ApiError(
            status_code=503,
            code="FILE_STORAGE_UNAVAILABLE",
            message="Private file storage is temporarily unavailable.",
            retryable=True,
        ) from exc

    if isinstance(exc, ProcessingDispatchError):
        raise ApiError(
            status_code=503,
            code="PROCESSING_UNAVAILABLE",
            message=str(exc),
            retryable=True,
        ) from exc
