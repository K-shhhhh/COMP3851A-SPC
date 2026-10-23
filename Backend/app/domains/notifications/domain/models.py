"""Notification-setting domain objects independent of HTTP and SQL."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NotificationPreferences:
    """Student-controlled MVP notification preferences."""

    new_group_messages: bool
    group_mentions: bool
