"""User-profile domain objects independent of HTTP and SQL."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UserProfile:
    """Editable and read-only fields shown on the student's profile page."""

    user_id: str
    full_name: str
    email: str
    programme: str | None
    year_of_study: int | None
    bio: str | None
    account_type: str
    status: str


@dataclass(frozen=True, slots=True)
class UserProfileChanges:
    """Allow-listed profile fields a student may change."""

    full_name: str | None = None
    programme: str | None = None
    year_of_study: int | None = None
    bio: str | None = None
    changed_fields: frozenset[str] = frozenset()
