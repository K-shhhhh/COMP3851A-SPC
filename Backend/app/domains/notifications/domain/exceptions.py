"""Notification-domain errors safe to translate at the HTTP boundary."""


class NotificationError(Exception):
    """Base class for expected notification failures."""


class NotificationNotFoundError(NotificationError):
    """Raised when an owned, currently authorized notification is absent."""


class InvalidNotificationCursorError(NotificationError):
    """Raised when a notification pagination cursor cannot be decoded."""
