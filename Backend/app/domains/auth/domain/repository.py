from abc import ABC, abstractmethod

from app.domains.auth.domain.models import AuthToken, User


class AuthRepository(ABC):

    @abstractmethod
    async def login(
        self,
        email: str,
        password: str,
    ) -> AuthToken:
        """Authenticate a user."""
        raise NotImplementedError

    @abstractmethod
    async def register(
        self,
        full_name: str,
        email: str,
        password: str,
    ) -> User:
        """Register a new user."""
        raise NotImplementedError