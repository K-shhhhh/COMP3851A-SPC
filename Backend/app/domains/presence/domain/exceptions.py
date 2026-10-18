"""Business errors raised by online-presence use cases."""


class PresenceError(Exception):
    """Base error for presence behavior."""


class PresenceUserNotFoundError(PresenceError):
    """Raised when an active account cannot be found."""


class PresencePermissionDeniedError(PresenceError):
    """Raised when a nonmember requests group presence."""
