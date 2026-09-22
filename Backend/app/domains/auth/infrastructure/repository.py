"""
PostgreSQL authentication repository placeholder.

The database developer will implement these methods after the authentication
schema and constraints are finalized. Local authentication currently uses
InMemoryAuthRepository instead.
"""

from app.domains.auth.domain.models import User, UserCredentials
from app.domains.auth.domain.repository import AuthRepository


class PostgreSQLAuthRepository(AuthRepository):
    """Future PostgreSQL implementation of the authentication contract."""

    async def get_credentials_by_email(
        self,
        email: str,
    ) -> UserCredentials | None:
        """Load credentials by email after PostgreSQL integration is added."""

        raise NotImplementedError(
            "PostgreSQL authentication is not implemented yet."
        )

    async def get_user_by_id(
        self,
        user_id: str,
    ) -> User | None:
        """Load a user by identifier after PostgreSQL integration is added."""

        raise NotImplementedError(
            "PostgreSQL authentication is not implemented yet."
        )

    async def create_user(
        self,
        full_name: str,
        email: str,
        hashed_password: str,
    ) -> User:
        """Persist a user and password hash after PostgreSQL integration."""

        raise NotImplementedError(
            "PostgreSQL authentication is not implemented yet."
        )


# import uuid
# from datetime import datetime, timezone

# from sqlalchemy import select
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.domains.auth.domain.models import (
#     User,
#     UserCredentials,
# )
# from app.domains.auth.domain.repository import AuthRepository

# from app.models.orm_models import (
#     User as ORMUser,
#     Group as ORMGroup,
#     Membership as ORMMembership,
#     ActivityStatus,
#     UserRole,
#     GroupType,
#     MemberRole,
# )


# class PostgreSQLAuthRepository(AuthRepository):

#     def __init__(self, session: AsyncSession) -> None:
#         self.session = session

#     @staticmethod
#     def _to_domain_user(user: ORMUser) -> User:
#         return User(
#             id=str(user.user_id),
#             full_name=user.fullname,
#             email=user.email,
#             role=user.user_role.value,
#             is_active=(
#                 user.status == ActivityStatus.ACTIVE
#                 and user.deleted_at is None
#             ),
#             created_at=user.created_at,
#         )

#     async def get_credentials_by_email(
#         self,
#         email: str,
#     ) -> UserCredentials | None:

#         stmt = select(ORMUser).where(
#             ORMUser.email == email,
#             ORMUser.deleted_at.is_(None),
#         )

#         orm_user = await self.session.scalar(stmt)

#         if orm_user is None:
#             return None

#         return UserCredentials(
#             user=self._to_domain_user(orm_user),
#             hashed_password=orm_user.password_hash,
#         )

#     async def get_user_by_id(
#         self,
#         user_id: str,
#     ) -> User | None:

#         try:
#             parsed_user_id = uuid.UUID(user_id)
#         except ValueError:
#             return None

#         stmt = select(ORMUser).where(
#             ORMUser.user_id == parsed_user_id,
#             ORMUser.deleted_at.is_(None),
#         )

#         orm_user = await self.session.scalar(stmt)

#         if orm_user is None:
#             return None

#         return self._to_domain_user(orm_user)

#     async def create_user(
#         self,
#         full_name: str,
#         email: str,
#         hashed_password: str,
#     ) -> User:

#         now = datetime.now(timezone.utc)

#         orm_user = ORMUser(
#             fullname=full_name,
#             email=email,
#             password_hash=hashed_password,
#             user_role=UserRole.STUDENT,
#             status=ActivityStatus.ACTIVE,
#             created_at=now,
#         )

#         self.session.add(orm_user)

#         try:
#             # Executes INSERT so the generated UUID is available.
#             await self.session.flush()

#             personal_group = ORMGroup(
#                 group_name=str(orm_user.user_id),
#                 group_type=GroupType.PERSONAL,
#                 created_by=orm_user.user_id,
#                 current_admin=orm_user.user_id,
#                 max_members=1,
#                 created_at=now,
#             )

#             self.session.add(personal_group)

#             # Generate the group's UUID before creating membership.
#             await self.session.flush()

#             personal_membership = ORMMembership(
#                 user_id=orm_user.user_id,
#                 group_id=personal_group.group_id,
#                 member_role=MemberRole.ADMIN,
#                 joined_at=now,
#             )

#             self.session.add(personal_membership)

#             # User + personal group + membership are committed together.
#             await self.session.commit()

#         except Exception:
#             await self.session.rollback()
#             raise

#         await self.session.refresh(orm_user)

#         return self._to_domain_user(orm_user)