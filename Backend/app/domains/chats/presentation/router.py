"""Authenticated endpoints for personal AI Assistant conversations."""

from uuid import UUID

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

from app.api.dependencies import (
    get_chat_service,
    get_current_user,
    get_note_service,
)
from app.api.error_handlers import ApiError
from app.core.config import settings
from app.domains.auth.domain.models import User
from app.domains.chats.application.services import ChatService
from app.domains.chats.domain.exceptions import (
    AnswerGenerationError,
    ChatNotFoundError,
    InvalidChatTitleError,
    InvalidQuestionError,
    NoProcessedNotesError,
    PromptInjectionDetectedError,
)
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
from app.domains.notes.presentation.schemas import (
    NoteResponse,
    NoteStatusResponse,
)
from app.domains.chats.presentation.schemas import (
    AskQuestionRequest,
    ChatExchangeResponse,
    ChatListItemResponse,
    ChatListResponse,
    ChatMessageListResponse,
    ChatMessageResponse,
    ChatResponse,
    CreateChatRequest,
    RenameChatRequest,
)


router = APIRouter(prefix="/chats", tags=["Personal Chat"])


@router.post(
    "/{chat_id}/attachments",
    response_model=NoteResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_personal_chat_attachment(
    chat_id: UUID,
    file: UploadFile = File(...),
    title: str | None = Form(default=None, max_length=150),
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
    note_service: NoteService = Depends(get_note_service),
) -> NoteResponse:
    """Upload a library-visible PDF to an owned personal conversation."""

    try:
        # Ownership is verified before the Notes module stores any bytes.
        await chat_service.get_chat(
            chat_id=str(chat_id),
            user_id=current_user.id,
        )
        data = await file.read(settings.MAX_NOTE_UPLOAD_SIZE_BYTES + 1)
        attachment = await note_service.upload_personal_chat_attachment(
            user_id=current_user.id,
            chat_id=str(chat_id),
            original_filename=file.filename,
            content_type=file.content_type,
            data=data,
            title=title,
        )
    except Exception as exc:
        _raise_chat_attachment_api_error(exc)
        raise
    finally:
        await file.close()

    return NoteResponse.from_attachment(attachment)


@router.get(
    "/{chat_id}/attachments/{attachment_id}/status",
    response_model=NoteStatusResponse,
)
async def get_personal_chat_attachment_status(
    chat_id: UUID,
    attachment_id: int,
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
    note_service: NoteService = Depends(get_note_service),
) -> NoteStatusResponse:
    """Return processing status for an owned personal-chat attachment."""

    try:
        await chat_service.get_chat(
            chat_id=str(chat_id),
            user_id=current_user.id,
        )
        attachment = await note_service.get_personal_chat_attachment(
            attachment_id=attachment_id,
            user_id=current_user.id,
            chat_id=str(chat_id),
        )
    except Exception as exc:
        _raise_chat_attachment_api_error(exc)
        raise

    return NoteStatusResponse.from_attachment(attachment)


@router.post("", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
async def create_chat(
    payload: CreateChatRequest,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    """Create a new personal AI Assistant conversation."""

    try:
        chat = await service.create_chat(
            user_id=current_user.id,
            title=payload.title,
        )
    except Exception as exc:
        _raise_chat_api_error(exc)
        raise

    return ChatResponse.from_chat(chat)


@router.get("", response_model=ChatListResponse)
async def list_chats(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> ChatListResponse:
    """List the authenticated student's personal conversations."""

    chats, total = await service.list_chats(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
    )
    return ChatListResponse(
        items=[ChatListItemResponse.from_chat(chat) for chat in chats],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{chat_id}", response_model=ChatResponse)
async def get_chat(
    chat_id: str,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    """Return one personal conversation owned by the current student."""

    try:
        chat = await service.get_chat(
            chat_id=chat_id,
            user_id=current_user.id,
        )
    except Exception as exc:
        _raise_chat_api_error(exc)
        raise

    return ChatResponse.from_chat(chat)


@router.patch("/{chat_id}", response_model=ChatResponse)
async def rename_chat(
    chat_id: str,
    payload: RenameChatRequest,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    """Rename one personal conversation owned by the current student."""

    try:
        chat = await service.rename_chat(
            chat_id=chat_id,
            user_id=current_user.id,
            title=payload.title,
        )
    except Exception as exc:
        _raise_chat_api_error(exc)
        raise

    return ChatResponse.from_chat(chat)


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    chat_id: str,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> Response:
    """Soft-delete one personal conversation owned by the current student."""

    try:
        await service.delete_chat(
            chat_id=chat_id,
            user_id=current_user.id,
        )
    except Exception as exc:
        _raise_chat_api_error(exc)
        raise

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{chat_id}/messages",
    response_model=ChatMessageListResponse,
)
async def list_messages(
    chat_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> ChatMessageListResponse:
    """Return oldest-first history for one owned personal conversation."""

    try:
        messages, total = await service.list_messages(
            chat_id=chat_id,
            user_id=current_user.id,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        _raise_chat_api_error(exc)
        raise

    return ChatMessageListResponse(
        chat_id=chat_id,
        items=[
            ChatMessageResponse.from_message(message)
            for message in messages
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "/{chat_id}/messages",
    response_model=ChatExchangeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ask_question(
    chat_id: str,
    payload: AskQuestionRequest,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> ChatExchangeResponse:
    """Synchronously return an answer grounded in the student's ready notes."""

    try:
        exchange = await service.ask_question(
            chat_id=chat_id,
            user_id=current_user.id,
            question=payload.content,
            response_format=payload.response_format,
        )
    except Exception as exc:
        _raise_chat_api_error(exc)
        raise

    return ChatExchangeResponse.from_exchange(
        chat_id=chat_id,
        exchange=exchange,
    )


def _raise_chat_api_error(exc: Exception) -> None:
    """Translate expected Chat failures into the shared error envelope."""

    if isinstance(exc, ChatNotFoundError):
        raise ApiError(
            status_code=404,
            code="CHAT_NOT_FOUND",
            message="The requested chat was not found.",
        ) from exc

    if isinstance(exc, NoProcessedNotesError):
        raise ApiError(
            status_code=409,
            code="NO_PROCESSED_NOTES",
            message=str(exc),
        ) from exc

    if isinstance(exc, PromptInjectionDetectedError):
        raise ApiError(
            status_code=422,
            code="PROMPT_INJECTION_DETECTED",
            message=(
                "The question contains instruction-overriding "
                "content that cannot be processed safely."
            ),
            retryable=False,
        ) from exc

    if isinstance(exc, (InvalidChatTitleError, InvalidQuestionError)):
        raise ApiError(
            status_code=422,
            code="VALIDATION_ERROR",
            message=str(exc),
        ) from exc

    if isinstance(exc, AnswerGenerationError):
        raise ApiError(
            status_code=503,
            code="ANSWER_GENERATION_FAILED",
            message=str(exc),
            retryable=True,
        ) from exc


def _raise_chat_attachment_api_error(exc: Exception) -> None:
    """Translate personal-chat attachment failures to the shared API shape."""

    if isinstance(exc, ChatNotFoundError):
        _raise_chat_api_error(exc)

    if isinstance(exc, AttachmentNotFoundError):
        raise ApiError(
            status_code=404,
            code="CHAT_ATTACHMENT_NOT_FOUND",
            message="The requested personal-chat attachment was not found.",
        ) from exc

    if isinstance(exc, FileTooLargeError):
        raise ApiError(
            status_code=413,
            code="FILE_TOO_LARGE",
            message=str(exc),
            details={"maximum_size_bytes": exc.maximum_size_bytes},
        ) from exc

    if isinstance(exc, UnsupportedFileTypeError):
        raise ApiError(
            status_code=415,
            code="UNSUPPORTED_FILE_TYPE",
            message=str(exc),
        ) from exc

    if isinstance(exc, (EmptyFileError, InvalidPdfError, UnsafeFilenameError)):
        raise ApiError(
            status_code=422,
            code="INVALID_CHAT_ATTACHMENT",
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
