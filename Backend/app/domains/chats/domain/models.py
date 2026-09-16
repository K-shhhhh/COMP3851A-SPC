"""Domain models for personal AI Assistant conversations.

These models do not depend on FastAPI, PostgreSQL, Redis, Celery, or a
particular AI provider. Study-group channels deliberately remain outside this
module for the current sprint.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class ChatMessageRole(StrEnum):
    """Roles supported by persisted personal-chat messages."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessageStatus(StrEnum):
    """Current synchronous-demo message states."""

    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class ChatSource:
    """Public citation connecting an answer to one authorized note chunk."""

    note_id: int
    note_title: str
    chunk_id: int
    page: int | None = None

    def __post_init__(self) -> None:
        """Validate citation identifiers and display metadata."""

        if self.note_id <= 0:
            raise ValueError("note_id must be greater than zero")
        if self.chunk_id <= 0:
            raise ValueError("chunk_id must be greater than zero")
        if not self.note_title.strip():
            raise ValueError("note_title must not be empty")
        if self.page is not None and self.page <= 0:
            raise ValueError("page must be greater than zero when provided")


@dataclass(frozen=True, slots=True)
class PersonalChat:
    """One AI Assistant conversation owned by exactly one student."""

    chat_id: str
    owner_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    last_message_preview: str | None = None
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        """Enforce conversation invariants shared by all adapters."""

        if not self.chat_id.strip():
            raise ValueError("chat_id must not be empty")
        if not self.owner_id.strip():
            raise ValueError("owner_id must not be empty")
        if not self.title.strip():
            raise ValueError("title must not be empty")
        if len(self.title) > 100:
            raise ValueError("title must not exceed 100 characters")


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """One persisted message inside a personal conversation."""

    message_id: int
    chat_id: str
    role: ChatMessageRole
    content: str
    status: ChatMessageStatus
    created_at: datetime
    sources: tuple[ChatSource, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate message content and source ownership rules."""

        if self.message_id <= 0:
            raise ValueError("message_id must be greater than zero")
        if not self.chat_id.strip():
            raise ValueError("chat_id must not be empty")
        if not self.content.strip():
            raise ValueError("content must not be empty")
        if self.role != ChatMessageRole.ASSISTANT and self.sources:
            raise ValueError("only assistant messages may contain sources")


@dataclass(frozen=True, slots=True)
class ChatExchange:
    """Completed synchronous question-and-answer result."""

    user_message: ChatMessage
    assistant_message: ChatMessage

