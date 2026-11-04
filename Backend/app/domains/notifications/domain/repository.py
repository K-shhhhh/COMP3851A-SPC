"""Persistence contract for per-user notification preferences."""

from abc import ABC, abstractmethod

from app.domains.notifications.domain.models import (
    Notification,
    NotificationPreferences,
)


class NotificationPreferenceRepository(ABC):

    @abstractmethod
    async def get_preferences(
        self,
        user_id: str,
    ) -> NotificationPreferences:
        """Return persisted values, using both ``True`` as creation defaults."""

        raise NotImplementedError

    @abstractmethod
    async def update_preferences(
        self,
        *,
        user_id: str,
        new_group_messages: bool | None,
        group_mentions: bool | None,
    ) -> NotificationPreferences:
        """Atomically apply supplied preference values and return the result."""

        raise NotImplementedError


class NotificationRepository(ABC):
    """Persistence contract for recipient-scoped in-app notifications."""

    @abstractmethod
    async def list_notifications(
        self,
        *,
        user_id: str,
        before_id: int | None,
        limit: int,
        unread_only: bool,
    ) -> tuple[list[Notification], bool]:
        """Return newest-first notifications and whether another page exists."""

        raise NotImplementedError

    @abstractmethod
    async def count_unread(self, *, user_id: str) -> int:
        """Count unread notifications still visible to the recipient."""

        raise NotImplementedError

    @abstractmethod
    async def mark_read(
        self,
        *,
        user_id: str,
        notification_id: int,
    ) -> Notification | None:
        """Mark one owned notification read and return its projection."""

        raise NotImplementedError

    @abstractmethod
    async def mark_all_read(self, *, user_id: str) -> int:
        """Mark all unread notifications belonging to the user as read."""

        raise NotImplementedError
