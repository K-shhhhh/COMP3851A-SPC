"""Persistence contract for the authenticated student's profile."""

from abc import ABC, abstractmethod

from app.domains.users.domain.models import UserProfile, UserProfileChanges


class UserProfileRepository(ABC):
    """Database adapter boundary owned by the database integration layer."""

    @abstractmethod
    async def get_profile(self, user_id: str) -> UserProfile | None:
        """Return an active, non-deleted user's profile or ``None``."""

        raise NotImplementedError

    @abstractmethod
    async def update_profile(
        self,
        *,
        user_id: str,
        changes: UserProfileChanges,
    ) -> UserProfile | None:
        """Atomically apply only supplied editable fields and return the row."""

        raise NotImplementedError
