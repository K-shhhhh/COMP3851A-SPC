"""HTTP schemas for notification preferences and the in-app inbox."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from app.domains.notifications.domain.models import (
    Notification,
    NotificationType,
)


class NotificationPreferencesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    new_group_messages: bool
    group_mentions: bool


class UpdateNotificationPreferencesRequest(BaseModel):
    new_group_messages: bool | None = None
    group_mentions: bool | None = None

    @model_validator(mode="after")
    def require_a_change(self) -> "UpdateNotificationPreferencesRequest":
        if not self.model_fields_set:
            raise ValueError("At least one notification preference is required.")
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("Notification preferences must be true or false.")
        return self


class NotificationActorResponse(BaseModel):
    user_id: str
    full_name: str


class NotificationResponse(BaseModel):
    notification_id: int
    type: NotificationType
    actor: NotificationActorResponse
    group_id: str
    group_name: str
    channel_id: str
    channel_name: str
    message_id: int
    message_preview: str
    created_at: datetime
    read_at: datetime | None

    @classmethod
    def from_notification(cls, value: Notification) -> "NotificationResponse":
        return cls(
            notification_id=value.notification_id,
            type=value.notification_type,
            actor=NotificationActorResponse(
                user_id=value.actor_user_id,
                full_name=value.actor_full_name,
            ),
            group_id=value.group_id,
            group_name=value.group_name,
            channel_id=value.channel_id,
            channel_name=value.channel_name,
            message_id=value.message_id,
            message_preview=value.message_preview,
            created_at=value.created_at,
            read_at=value.read_at,
        )


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    next_cursor: str | None


class UnreadNotificationCountResponse(BaseModel):
    unread_count: int


class MarkAllNotificationsReadResponse(BaseModel):
    marked_read_count: int
