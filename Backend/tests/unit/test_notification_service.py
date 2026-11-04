"""Unit coverage for in-app notification inbox behaviour."""

from datetime import datetime, timezone

import pytest

from app.domains.notifications.application.services import NotificationService
from app.domains.notifications.domain.exceptions import (
    InvalidNotificationCursorError,
    NotificationNotFoundError,
)
from app.domains.notifications.domain.models import Notification, NotificationType
from app.domains.notifications.domain.repository import NotificationRepository


pytestmark = pytest.mark.asyncio


class FakeNotificationRepository(NotificationRepository):
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.items = [
            Notification(
                notification_id=value,
                notification_type=NotificationType.NEW_GROUP_MESSAGE,
                actor_user_id="actor",
                actor_full_name="Student",
                group_id="group",
                group_name="Study Group",
                channel_id="channel",
                channel_name="general",
                message_id=value,
                message_preview=f"Message {value}",
                created_at=now,
                read_at=None,
            )
            for value in (3, 2, 1)
        ]

    async def list_notifications(
        self, *, user_id, before_id, limit, unread_only
    ):
        del user_id, unread_only
        values = [
            item for item in self.items
            if before_id is None or item.notification_id < before_id
        ]
        return values[:limit], len(values) > limit

    async def count_unread(self, *, user_id):
        del user_id
        return sum(item.read_at is None for item in self.items)

    async def mark_read(self, *, user_id, notification_id):
        del user_id
        return next(
            (item for item in self.items if item.notification_id == notification_id),
            None,
        )

    async def mark_all_read(self, *, user_id):
        del user_id
        return len(self.items)


async def test_notification_cursor_round_trip() -> None:
    service = NotificationService(FakeNotificationRepository())
    first = await service.list_notifications(
        user_id="student", cursor=None, limit=2, unread_only=False
    )
    assert [item.notification_id for item in first.items] == [3, 2]
    assert first.next_cursor is not None

    second = await service.list_notifications(
        user_id="student",
        cursor=first.next_cursor,
        limit=2,
        unread_only=False,
    )
    assert [item.notification_id for item in second.items] == [1]
    assert second.next_cursor is None


async def test_invalid_notification_cursor_is_rejected() -> None:
    service = NotificationService(FakeNotificationRepository())
    with pytest.raises(InvalidNotificationCursorError):
        await service.list_notifications(
            user_id="student", cursor="not-a-cursor", limit=20, unread_only=False
        )


async def test_marking_unknown_notification_is_rejected() -> None:
    service = NotificationService(FakeNotificationRepository())
    with pytest.raises(NotificationNotFoundError):
        await service.mark_read(user_id="student", notification_id=999)
