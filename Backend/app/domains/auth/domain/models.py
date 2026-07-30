from dataclasses import dataclass


@dataclass(slots=True)
class User:
    """Domain entity representing an authenticated user."""

    id: int
    full_name: str
    email: str


@dataclass(slots=True)
class AuthToken:
    """Domain entity representing an authentication token."""

    access_token: str
    token_type: str = "bearer"