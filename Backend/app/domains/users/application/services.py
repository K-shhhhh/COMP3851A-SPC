# Users use cases depend on repository interfaces, not HTTP or SQL.
# Current methods delegate to repositories; authorization and business rules still need implementation.
from app.domains.users.domain.models import User
from app.domains.users.domain.repository import UserRepository


class UserService:

    def __init__(
        self,
        repository: UserRepository,
    ):
        self.repository = repository

    async def get_all_users(self):

        return await self.repository.get_all_users()

    async def get_user_by_id(
        self,
        user_id: int,
    ):

        return await self.repository.get_user_by_id(user_id)

    async def update_user(
        self,
        user: User,
    ):

        return await self.repository.update_user(user)
