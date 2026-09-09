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


@dataclass(frozen=True, slots=True)
class WebSocketTicket:
    """Short-lived credential used only to open a WebSocket connection."""

    ticket: str
    expires_in: int
