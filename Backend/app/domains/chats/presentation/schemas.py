"""Public validation and response schemas for personal chat."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.domains.chats.domain.models import (
    ChatExchange,
    ChatMessage,
    ChatMessageRole,
    ChatMessageStatus,
    ChatSource,
    PersonalChat,
)


class CreateChatRequest(BaseModel):
    """Optional display title for a new AI Assistant conversation."""

    title: str | None = Field(default=None, max_length=100)


class RenameChatRequest(BaseModel):
    """Replacement display title for an owned conversation."""

    title: str = Field(min_length=1, max_length=100)


class AskQuestionRequest(BaseModel):
    """One personal-chat question submitted by the authenticated student."""

    content: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    """Public metadata for one personal AI Assistant conversation."""

    id: str
    title: str
    type: Literal["personal"] = "personal"
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_chat(cls, chat: PersonalChat) -> "ChatResponse":
        """Map an internal owner-bearing model to a safe response."""

        return cls(
            id=chat.chat_id,
            title=chat.title,
            created_at=chat.created_at,
            updated_at=chat.updated_at,
        )


class ChatListItemResponse(ChatResponse):
    """Compact chat metadata displayed in the conversation sidebar."""

    last_message_preview: str | None

    @classmethod
    def from_chat(cls, chat: PersonalChat) -> "ChatListItemResponse":
        """Map a chat and its current preview to a list item."""

        return cls(
            id=chat.chat_id,
            title=chat.title,
            created_at=chat.created_at,
            updated_at=chat.updated_at,
            last_message_preview=chat.last_message_preview,
        )


class ChatListResponse(BaseModel):
    """Paginated list of the current student's personal conversations."""

    items: list[ChatListItemResponse]
    page: int
    page_size: int
    total: int


class ChatSourceResponse(BaseModel):
    """Safe note citation displayed with an assistant answer."""

    note_id: int
    note_title: str
    chunk_id: int
    page: int | None

    @classmethod
    def from_source(cls, source: ChatSource) -> "ChatSourceResponse":
        """Map a validated source to the public citation shape."""

        return cls(
            note_id=source.note_id,
            note_title=source.note_title,
            chunk_id=source.chunk_id,
            page=source.page,
        )


class ChatMessageResponse(BaseModel):
    """One user, assistant, or system message in conversation history."""

    id: int
    role: ChatMessageRole
    content: str
    status: ChatMessageStatus
    sources: list[ChatSourceResponse]
    created_at: datetime

    @classmethod
    def from_message(cls, message: ChatMessage) -> "ChatMessageResponse":
        """Map an internal chat message to the public contract."""

        return cls(
            id=message.message_id,
            role=message.role,
            content=message.content,
            status=message.status,
            sources=[
                ChatSourceResponse.from_source(source)
                for source in message.sources
            ],
            created_at=message.created_at,
        )


class ChatMessageListResponse(BaseModel):
    """Paginated oldest-first history for one personal conversation."""

    chat_id: str
    items: list[ChatMessageResponse]
    page: int
    page_size: int
    total: int


class ChatExchangeResponse(BaseModel):
    """Completed synchronous question and grounded answer."""

    chat_id: str
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse

    @classmethod
    def from_exchange(
        cls,
        *,
        chat_id: str,
        exchange: ChatExchange,
    ) -> "ChatExchangeResponse":
        """Map both persisted messages to one synchronous API response."""

        return cls(
            chat_id=chat_id,
            user_message=ChatMessageResponse.from_message(
                exchange.user_message
            ),
            assistant_message=ChatMessageResponse.from_message(
                exchange.assistant_message
            ),
        )

