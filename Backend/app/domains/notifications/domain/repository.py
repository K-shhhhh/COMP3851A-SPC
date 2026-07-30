from abc import ABC, abstractmethod

from app.domains.notifications.domain.models import Notification


class NotificationRepository(ABC):

    @abstractmethod
    async def get_all_notifications(self) -> list[Notification]:
        raise NotImplementedError

    @abstractmethod
    async def get_notification_by_id(
        self,
        notification_id: int,
    ) -> Notification:
        raise NotImplementedError

    @abstractmethod
    async def create_notification(
        self,
        title: str,
        message: str,
        recipient_id: int,
    ) -> Notification:
        raise NotImplementedError

    @abstractmethod
    async def mark_as_read(
        self,
        notification_id: int,
    ) -> Notification:
        raise NotImplementedError

    @abstractmethod
    async def delete_notification(
        self,
        notification_id: int,
    ) -> None:
        raise NotImplementedError