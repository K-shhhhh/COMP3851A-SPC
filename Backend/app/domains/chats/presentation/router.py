"""Authenticated endpoints for personal AI Assistant conversations."""

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import get_chat_service, get_current_user
from app.api.error_handlers import ApiError
from app.domains.auth.domain.models import User
from app.domains.chats.application.services import ChatService
from app.domains.chats.domain.exceptions import (
    AnswerGenerationError,
    ChatNotFoundError,
    InvalidChatTitleError,
    InvalidQuestionError,
    NoProcessedNotesError,
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

