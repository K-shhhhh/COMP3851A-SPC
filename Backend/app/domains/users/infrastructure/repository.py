# DEMO users repository: returns constructed objects instead of executing SQL.
# Do not interpret successful responses as persisted data or authenticated access.
from app.domains.users.domain.models import User
from app.domains.users.domain.repository import UserRepository


class PostgreSQLUserRepository(UserRepository):

    async def get_all_users(self) -> list[User]:

        return [
            User(
                id=1,
                full_name="John Doe",
                email="john@example.com",
                role="Student",
            ),
            User(
                id=2,
                full_name="Jane Smith",
                email="jane@example.com",
                role="Lecturer",
            ),
        ]

    async def get_user_by_id(
        self,
        user_id: int,
    ) -> User:

        return User(
            id=user_id,
            full_name="John Doe",
            email="john@example.com",
            role="Student",
        )

    async def update_user(
        self,
        user: User,
    ) -> User:

        return user


# from datetime import datetime, timezone

# from sqlalchemy import select
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.domains.users.domain.models import User as DomainUser
# from app.domains.users.domain.repository import UserRepository
# from app.models.orm_models import (
#     User as ORMUser,
#     UserRole,
# )


# class PostgreSQLUserRepository(UserRepository):

#     def __init__(self, session: AsyncSession) -> None:
#         self.session = session

#     @staticmethod
#     def _to_domain(user: ORMUser) -> DomainUser:
#         return DomainUser(
#             id=user.user_id,
#             full_name=user.fullname,
#             email=user.email,
#             role=user.user_role.value,
#         )

#     async def get_all_users(self) -> list[DomainUser]:
#         stmt = (
#             select(ORMUser)
#             .where(ORMUser.deleted_at.is_(None))
#             .order_by(ORMUser.created_at)
#         )

#         result = await self.session.scalars(stmt)
#         users = result.all()

#         return [
#             self._to_domain(user)
#             for user in users
#         ]

#     async def get_user_by_id(
#         self,
#         user_id,
#     ) -> DomainUser:
#         stmt = select(ORMUser).where(
#             ORMUser.user_id == user_id,
#             ORMUser.deleted_at.is_(None),
#         )

#         orm_user = await self.session.scalar(stmt)

#         if orm_user is None:
#             raise LookupError(f"User {user_id} not found")

#         return self._to_domain(orm_user)

#     async def update_user(
#         self,
#         user: DomainUser,
#     ) -> DomainUser:
#         stmt = select(ORMUser).where(
#             ORMUser.user_id == user.id,
#             ORMUser.deleted_at.is_(None),
#         )

#         orm_user = await self.session.scalar(stmt)

#         if orm_user is None:
#             raise LookupError(f"User {user.id} not found")

#         orm_user.fullname = user.full_name
#         orm_user.email = user.email
#         orm_user.user_role = UserRole(user.role)
#         orm_user.last_updated_at = datetime.now(timezone.utc)

#         await self.session.commit()
#         await self.session.refresh(orm_user)

#         return self._to_domain(orm_user)