from app.domains.notifications.domain.models import Notification
from app.domains.notifications.domain.repository import (
    NotificationRepository,
)


class PostgreSQLNotificationRepository(
    NotificationRepository
):

    async def get_all_notifications(self) -> list[Notification]:

        return [
            Notification(
                id=1,
                title="Study Reminder",
                message="Your study session starts in 30 minutes.",
                recipient_id=1,
                is_read=False,
            )
        ]

    async def get_notification_by_id(
        self,
        notification_id: int,
    ) -> Notification:

        return Notification(
            id=notification_id,
            title="Study Reminder",
            message="Your study session starts in 30 minutes.",
            recipient_id=1,
            is_read=False,
        )

    async def create_notification(
        self,
        title: str,
        message: str,
        recipient_id: int,
    ) -> Notification:

        return Notification(
            id=2,
            title=title,
            message=message,
            recipient_id=recipient_id,
            is_read=False,
        )

    async def mark_as_read(
        self,
        notification_id: int,
    ) -> Notification:

        return Notification(
            id=notification_id,
            title="Study Reminder",
            message="Notification marked as read.",
            recipient_id=1,
            is_read=True,
        )

    async def delete_notification(
        self,
        notification_id: int,
    ) -> None:

        return None