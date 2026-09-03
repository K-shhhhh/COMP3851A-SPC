# Notifications use cases depend on repository interfaces, not HTTP or SQL.
# Current methods delegate to repositories; authorization and business rules still need implementation.
# Owner: Krish implements this application/background/AI behavior.
from app.domains.notifications.domain.repository import (
    NotificationRepository,
)


class NotificationService:

    def __init__(
        self,
        repository: NotificationRepository,
    ):
        self.repository = repository

    async def get_all_notifications(self):

        return await self.repository.get_all_notifications()

    async def get_notification_by_id(
        self,
        notification_id: int,
    ):

        return await self.repository.get_notification_by_id(
            notification_id
        )

    async def create_notification(
        self,
        title: str,
        message: str,
        recipient_id: int,
    ):

        return await self.repository.create_notification(
            title,
            message,
            recipient_id,
        )

    async def mark_as_read(
        self,
        notification_id: int,
    ):

        return await self.repository.mark_as_read(
            notification_id
        )

    async def delete_notification(
        self,
        notification_id: int,
    ):

        await self.repository.delete_notification(
            notification_id
        )
