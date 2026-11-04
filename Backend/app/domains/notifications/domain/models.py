"""Notification domain objects independent of HTTP and SQL."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


@dataclass(frozen=True, slots=True)
class NotificationPreferences:
    """Student-controlled MVP notification preferences."""

    new_group_messages: bool
    group_mentions: bool


class NotificationType(str, Enum):
    """In-app notification categories supported by the student MVP."""

    NEW_GROUP_MESSAGE = "new_group_message"
    GROUP_MENTION = "group_mention"


@dataclass(frozen=True, slots=True)
class Notification:
    """One authorized in-app notification projection."""

    notification_id: int
    notification_type: NotificationType
    actor_user_id: str
    actor_full_name: str
    group_id: str
    group_name: str
    channel_id: str
    channel_name: str
    message_id: int
    message_preview: str
    created_at: datetime
    read_at: datetime | None


@dataclass(frozen=True, slots=True)
class NotificationPage:
    """Cursor-paginated notifications belonging to one user."""

    items: tuple[Notification, ...]
    next_cursor: str | None
