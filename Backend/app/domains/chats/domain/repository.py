"""Persistence contract for personal chats and their message history."""

from abc import ABC, abstractmethod
from datetime import datetime

from app.domains.chats.domain.models import (
    ChatMessage,
    ChatMessageRole,
    ChatSource,
    PersonalChat,
)


class ChatRepository(ABC):
    """Define storage operations without exposing PostgreSQL to use cases."""

    @abstractmethod
    async def create_chat(self, *, owner_id: str, title: str) -> PersonalChat:
        """Create and return one student-owned personal conversation."""

        raise NotImplementedError

    @abstractmethod
    async def list_owned_chats(
        self,
        *,
        owner_id: str,
        offset: int,
        limit: int,
    ) -> tuple[list[PersonalChat], int]:
        """Return one page of non-deleted chats owned by a student."""

        raise NotImplementedError

    @abstractmethod
    async def get_owned_chat(
        self,
        *,
        chat_id: str,
        owner_id: str,
    ) -> PersonalChat | None:
        """Return a chat only when it belongs to the supplied student."""

        raise NotImplementedError

    @abstractmethod
    async def rename_owned_chat(
        self,
        *,
        chat_id: str,
        owner_id: str,
        title: str,
    ) -> PersonalChat | None:
        """Rename an owned chat and return the updated value."""

        raise NotImplementedError

    @abstractmethod
    async def soft_delete_owned_chat(
        self,
        *,
        chat_id: str,
        owner_id: str,
        deleted_at: datetime,
    ) -> bool:
        """Soft-delete an owned chat without exposing whether another exists."""

        raise NotImplementedError

    @abstractmethod
    async def create_message(
        self,
        *,
        chat_id: str,
        role: ChatMessageRole,
        content: str,
        sources: tuple[ChatSource, ...] = (),
    ) -> ChatMessage:
        """Persist a completed message after ownership has been verified."""

        raise NotImplementedError

    @abstractmethod
    async def list_messages(
        self,
        *,
        chat_id: str,
        offset: int,
        limit: int,
    ) -> tuple[list[ChatMessage], int]:
        """Return one oldest-first page of messages for an authorized chat."""

        raise NotImplementedError

