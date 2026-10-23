"""Authenticated student-profile use cases."""

from app.domains.users.domain.exceptions import UserProfileNotFoundError
from app.domains.users.domain.models import UserProfile, UserProfileChanges
from app.domains.users.domain.repository import UserProfileRepository


class UserProfileService:
    """Read and update only the currently authenticated user's profile."""

    def __init__(self, repository: UserProfileRepository) -> None:
        self.repository = repository

    async def get_profile(self, user_id: str) -> UserProfile:
        profile = await self.repository.get_profile(user_id)
        if profile is None:
            raise UserProfileNotFoundError("The user profile was not found.")
        return profile

    async def update_profile(
        self,
        *,
        user_id: str,
        changes: UserProfileChanges,
    ) -> UserProfile:
        profile = await self.repository.update_profile(
            user_id=user_id,
            changes=changes,
        )
        if profile is None:
            raise UserProfileNotFoundError("The user profile was not found.")
        return profile
