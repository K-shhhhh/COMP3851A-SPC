"""PostgreSQL repository implementation for authentication.

This adapter converts between SQLAlchemy ORM objects and authentication
domain models. PostgreSQL UUID values remain UUID objects inside this layer
and are exposed as strings to the domain and API layers.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.domain.exceptions import (
    EmailAlreadyRegisteredError,
)
from app.domains.auth.domain.models import (
    User,
    UserCredentials,
)
from app.domains.auth.domain.password_repository import (
    PasswordChangeRepository,
)
from app.domains.auth.domain.repository import AuthRepository
from app.models.orm_models import (
    ActivityStatus,
    Group as ORMGroup,
    GroupType,
    MemberRole,
    Membership as ORMMembership,
    User as ORMUser,
    UserRole,
)


class PostgreSQLPasswordChangeRepository(PasswordChangeRepository):
    """Persist authenticated password changes for active, non-deleted users."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_password_hash(self, user_id: str) -> str | None:
        """Return the active user's password hash, never plaintext."""

        try:
            parsed_user_id = uuid.UUID(user_id)
        except (TypeError, ValueError):
            return None

        statement = select(ORMUser.password_hash).where(
            ORMUser.user_id == parsed_user_id,
            ORMUser.status == ActivityStatus.ACTIVE,
            ORMUser.deleted_at.is_(None),
        )

        return await self.session.scalar(statement)

    async def update_password_hash(
        self,
        *,
        user_id: str,
        password_hash: str,
    ) -> bool:
        """Atomically replace the hash and return whether a row was updated."""

        try:
            parsed_user_id = uuid.UUID(user_id)
        except (TypeError, ValueError):
            return False

        now = datetime.now(timezone.utc)
        statement = (
            update(ORMUser)
            .where(
                ORMUser.user_id == parsed_user_id,
                ORMUser.status == ActivityStatus.ACTIVE,
                ORMUser.deleted_at.is_(None),
            )
            .values(
                password_hash=password_hash,
                last_updated_at=now,
            )
            .returning(ORMUser.user_id)
        )

        try:
            result = await self.session.execute(statement)
            updated_id = result.scalar_one_or_none()
            if updated_id is None:
                return False

            await self.session.commit()
            return True

        except Exception:
            await self.session.rollback()
            raise


class PostgreSQLAuthRepository(
    PostgreSQLPasswordChangeRepository,
    AuthRepository,
):
    """Persist authentication data using one request-scoped session."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    @staticmethod
    def _to_domain_user(orm_user: ORMUser) -> User:
        """Convert a PostgreSQL user record into an authentication user."""

        return User(
            id=str(orm_user.user_id),
            full_name=orm_user.fullname,
            email=orm_user.email,
            role=orm_user.user_role.value,
            is_active=(
                orm_user.status == ActivityStatus.ACTIVE
                and orm_user.deleted_at is None
            ),
            created_at=orm_user.created_at,
            email_verified_at=orm_user.email_verified_at,
        )

    async def get_credentials_by_email(
        self,
        email: str,
    ) -> UserCredentials | None:
        """Return credentials associated with a normalized email address.

        Deleted and deactivated accounts are returned as inactive users. This
        allows the application service to reject them consistently and avoids
        attempting to create another record that violates the unique-email
        constraint.
        """

        statement = select(ORMUser).where(
            ORMUser.email == email,
        )

        orm_user = await self.session.scalar(statement)

        if orm_user is None:
            return None

        return UserCredentials(
            user=self._to_domain_user(orm_user),
            hashed_password=orm_user.password_hash,
        )

    async def get_user_by_id(
        self,
        user_id: str,
    ) -> User | None:
        """Return an active, non-deleted user by string UUID."""

        try:
            parsed_user_id = uuid.UUID(user_id)
        except (TypeError, ValueError):
            return None

        statement = select(ORMUser).where(
            ORMUser.user_id == parsed_user_id,
            ORMUser.deleted_at.is_(None),
        )

        orm_user = await self.session.scalar(statement)

        if orm_user is None:
            return None

        domain_user = self._to_domain_user(orm_user)

        if not domain_user.is_active:
            return None

        return domain_user

    async def create_user(
        self,
        full_name: str,
        email: str,
        hashed_password: str,
        email_verified_at: datetime | None = None,
    ) -> User:
        """Create a user, personal group, and membership atomically.

        All three records are committed together. If any insert fails, the
        transaction is rolled back so a partially registered account cannot
        remain in the database.
        """

        now = datetime.now(timezone.utc)

        orm_user = ORMUser(
            fullname=full_name,
            email=email,
            password_hash=hashed_password,
            user_role=UserRole.STUDENT,
            status=ActivityStatus.ACTIVE,
            created_at=now,
            email_verified_at=email_verified_at,
        )

        self.session.add(orm_user)

        try:
            # Flush the user insert so SQLAlchemy generates the UUID.
            await self.session.flush()

            personal_group = ORMGroup(
                group_name=str(orm_user.user_id),
                group_type=GroupType.PERSONAL,
                description="Personal AI Assistant",
                created_by=orm_user.user_id,
                current_owner=orm_user.user_id,
                max_members=1,
                created_at=now,
            )

            self.session.add(personal_group)

            # Generate the personal group's UUID before making membership.
            await self.session.flush()

            personal_membership = ORMMembership(
                user_id=orm_user.user_id,
                group_id=personal_group.group_id,
                member_role=MemberRole.OWNER,
                joined_at=now,
            )

            self.session.add(personal_membership)

            # User, group and membership succeed or fail together.
            await self.session.commit()

        except IntegrityError as error:
            await self.session.rollback()

            # The database remains the final protection against two
            # simultaneous registrations using the same email address.
            raise EmailAlreadyRegisteredError(
                "An account with this email already exists."
            ) from error

        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(orm_user)

        return self._to_domain_user(orm_user)
