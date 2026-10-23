"""User-profile errors without transport-specific behaviour."""


class UserProfileNotFoundError(Exception):
    """Raised when the authenticated account no longer has a profile."""
