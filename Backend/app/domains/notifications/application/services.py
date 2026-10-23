"""Notification-preference use cases."""

from app.domains.notifications.domain.repository import (
    NotificationPreferenceRepository,
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
