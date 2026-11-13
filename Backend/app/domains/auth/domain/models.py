"""
Authentication domain models.

These objects are independent of FastAPI and PostgreSQL.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class User:
    """A user safe to return to other application layers."""

    id: str
    full_name: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    email_verified_at: datetime | None = None

    @property
    def is_email_verified(self) -> bool:
        """Return whether ownership of the account email was confirmed."""

        return self.email_verified_at is not None


@dataclass(frozen=True, slots=True)
class UserCredentials:
    """
    A user record containing the password hash.

    This object must never be returned by an API endpoint.
    """

    user: User
    hashed_password: str


@dataclass(frozen=True, slots=True)
class AuthSession:
    """Successful login result returned by the authentication service."""

    access_token: str
    token_type: str
    expires_in: int
    user: User
    refresh_token: str | None = None


@dataclass(frozen=True, slots=True)
class WebSocketTicket:
    """Short-lived credential used only to open a WebSocket connection."""

    ticket: str
    expires_in: int


@dataclass(frozen=True, slots=True)
class EmailVerificationChallenge:
    """Latest one-time verification challenge for one account."""

    id: str
    user_id: str
    email: str
    code_hash: str
    expires_at: datetime
    attempt_count: int
    created_at: datetime
    consumed_at: datetime | None = None
