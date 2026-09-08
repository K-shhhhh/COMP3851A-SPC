# Users repository contract used by the application service.
# The database developer implements these operations; abstract methods provide no storage.
from abc import ABC, abstractmethod

from app.domains.users.domain.models import User


class UserRepository(ABC):

    @abstractmethod
    async def get_all_users(self) -> list[User]:
        raise NotImplementedError

    @abstractmethod
    async def get_user_by_id(
        self,
        user_id: int,
    ) -> User:
        raise NotImplementedError

    @abstractmethod
    async def update_user(
        self,
        user: User,
    ) -> User:
        raise NotImplementedError
