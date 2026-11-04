"""Notification preferences and in-app notification use cases."""

import base64
import binascii

from app.domains.notifications.domain.exceptions import (
    InvalidNotificationCursorError,
    NotificationNotFoundError,
)
from app.domains.notifications.domain.models import NotificationPage
from app.domains.notifications.domain.repository import (
    NotificationPreferenceRepository,
    NotificationRepository,
)


class NotificationPreferenceService:

    def __init__(self, repository: NotificationPreferenceRepository) -> None:
        self.repository = repository

    async def get_preferences(self, user_id: str):
        return await self.repository.get_preferences(user_id)

    async def update_preferences(
        self,
        *,
        user_id: str,
        new_group_messages: bool | None,
        group_mentions: bool | None,
    ):
        return await self.repository.update_preferences(
            user_id=user_id,
            new_group_messages=new_group_messages,
            group_mentions=group_mentions,
        )


class NotificationService:
    """Read and acknowledge in-app notifications for one recipient."""

    def __init__(self, repository: NotificationRepository) -> None:
        self.repository = repository

    @staticmethod
    def _encode_cursor(notification_id: int) -> str:
        encoded = base64.urlsafe_b64encode(str(notification_id).encode("ascii"))
        return encoded.decode("ascii").rstrip("=")

    @staticmethod
    def _decode_cursor(cursor: str | None) -> int | None:
        if cursor is None:
            return None
        try:
            padding = "=" * (-len(cursor) % 4)
            decoded = base64.urlsafe_b64decode(cursor + padding).decode("ascii")
            notification_id = int(decoded)
        except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
            raise InvalidNotificationCursorError(
                "The notification cursor is invalid."
            ) from exc
        if notification_id <= 0:
            raise InvalidNotificationCursorError(
                "The notification cursor is invalid."
            )
        return notification_id

    async def list_notifications(
        self,
        *,
        user_id: str,
        cursor: str | None,
        limit: int,
        unread_only: bool,
    ) -> NotificationPage:
        before_id = self._decode_cursor(cursor)
        items, has_more = await self.repository.list_notifications(
            user_id=user_id,
            before_id=before_id,
            limit=limit,
            unread_only=unread_only,
        )
        next_cursor = None
        if has_more and items:
            next_cursor = self._encode_cursor(items[-1].notification_id)
        return NotificationPage(items=tuple(items), next_cursor=next_cursor)

    async def count_unread(self, *, user_id: str) -> int:
        return await self.repository.count_unread(user_id=user_id)

    async def mark_read(self, *, user_id: str, notification_id: int):
        notification = await self.repository.mark_read(
            user_id=user_id,
            notification_id=notification_id,
        )
        if notification is None:
            raise NotificationNotFoundError("Notification not found.")
        return notification

    async def mark_all_read(self, *, user_id: str) -> int:
        return await self.repository.mark_all_read(user_id=user_id)
