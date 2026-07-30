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