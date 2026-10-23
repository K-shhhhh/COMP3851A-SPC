"""Persistence contract for per-user notification preferences."""

from abc import ABC, abstractmethod

from app.domains.notifications.domain.models import NotificationPreferences


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
