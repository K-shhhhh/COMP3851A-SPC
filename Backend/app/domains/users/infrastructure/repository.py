"""PostgreSQL repository implementation for student user profiles."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.users.domain.models import UserProfile, UserProfileChanges
from app.domains.users.domain.repository import UserProfileRepository
from app.models.orm_models import (
    ActivityStatus,
    User as ORMUser,
    UserProfile as ORMUserProfile,
)

_EDITABLE_PROFILE_FIELDS = frozenset(
    {"full_name", "programme", "year_of_study", "bio"}
)
_PROFILE_TABLE_FIELDS = frozenset({"programme", "year_of_study", "bio"})


class PostgreSQLUserProfileRepository(UserProfileRepository):
    """Persist and read active student profiles using one request-scoped session."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _parse_uuid(user_id: str) -> uuid.UUID | None:
        try:
            return uuid.UUID(user_id)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_domain_profile(
        orm_user: ORMUser,
        orm_profile: ORMUserProfile | None,
    ) -> UserProfile:
        return UserProfile(
            user_id=str(orm_user.user_id),
            full_name=orm_user.fullname,
            email=orm_user.email,
            programme=orm_profile.programme if orm_profile is not None else None,
            year_of_study=(
                orm_profile.year_of_study if orm_profile is not None else None
            ),
            bio=orm_profile.bio if orm_profile is not None else None,
            account_type=orm_user.user_role.value,
            status=orm_user.status.value,
        )

    @staticmethod
    def _validate_changes(changes: UserProfileChanges) -> None:
        unknown_fields = changes.changed_fields - _EDITABLE_PROFILE_FIELDS
        if unknown_fields:
            raise ValueError(
                f"Unsupported profile fields: {', '.join(sorted(unknown_fields))}"
            )

        if "full_name" in changes.changed_fields:
            if changes.full_name is None or not changes.full_name.strip():
                raise ValueError("Full name cannot be null or empty.")

        if (
            "programme" in changes.changed_fields
            and changes.programme is not None
            and len(changes.programme) > 120
        ):
            raise ValueError("Programme must not exceed 120 characters.")

        if (
            "year_of_study" in changes.changed_fields
            and changes.year_of_study is not None
            and not (1 <= changes.year_of_study <= 10)
        ):
            raise ValueError("Year of study must be between 1 and 10.")

        if (
            "bio" in changes.changed_fields
            and changes.bio is not None
            and len(changes.bio) > 500
        ):
            raise ValueError("Bio must not exceed 500 characters.")

    async def get_profile(self, user_id: str) -> UserProfile | None:
        """Return an active, non-deleted user's profile or ``None``."""

        parsed_user_id = self._parse_uuid(user_id)
        if parsed_user_id is None:
            return None

        statement = (
            select(ORMUser, ORMUserProfile)
            .outerjoin(
                ORMUserProfile,
                ORMUserProfile.user_id == ORMUser.user_id,
            )
            .where(
                ORMUser.user_id == parsed_user_id,
                ORMUser.status == ActivityStatus.ACTIVE,
                ORMUser.deleted_at.is_(None),
            )
        )

        row = (await self.session.execute(statement)).first()
        if row is None:
            return None

        orm_user, orm_profile = row
        return self._to_domain_profile(orm_user, orm_profile)

    async def update_profile(
        self,
        *,
        user_id: str,
        changes: UserProfileChanges,
    ) -> UserProfile | None:
        """Atomically apply only supplied editable fields and return the row."""

        parsed_user_id = self._parse_uuid(user_id)
        if parsed_user_id is None:
            return None

        self._validate_changes(changes)

        user_statement = select(ORMUser).where(
            ORMUser.user_id == parsed_user_id,
            ORMUser.status == ActivityStatus.ACTIVE,
            ORMUser.deleted_at.is_(None),
        )
        orm_user = await self.session.scalar(user_statement)
        if orm_user is None:
            return None

        profile_statement = select(ORMUserProfile).where(
            ORMUserProfile.user_id == parsed_user_id,
        )
        orm_profile = await self.session.scalar(profile_statement)

        try:
            now = datetime.now(timezone.utc)
            modified = False

            if "full_name" in changes.changed_fields:
                assert changes.full_name is not None
                orm_user.fullname = changes.full_name
                modified = True

            supplied_profile_fields = (
                changes.changed_fields & _PROFILE_TABLE_FIELDS
            )
            if supplied_profile_fields:
                if orm_profile is None:
                    orm_profile = ORMUserProfile(user_id=parsed_user_id)
                    self.session.add(orm_profile)

                if "programme" in supplied_profile_fields:
                    orm_profile.programme = changes.programme
                if "year_of_study" in supplied_profile_fields:
                    orm_profile.year_of_study = changes.year_of_study
                if "bio" in supplied_profile_fields:
                    orm_profile.bio = changes.bio
                modified = True

            if modified:
                orm_user.last_updated_at = now
                await self.session.commit()

        except Exception:
            await self.session.rollback()
            raise

        return self._to_domain_profile(orm_user, orm_profile)
