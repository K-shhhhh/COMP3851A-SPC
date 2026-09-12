"""
Repository contract required by authentication.

The database developer implements this interface using PostgreSQL.
"""

from abc import ABC, abstractmethod

from app.domains.auth.domain.models import User, UserCredentials


class AuthRepository(ABC):
    """Define persistence operations required by authentication use cases."""

    @abstractmethod
    async def get_credentials_by_email(
        self,
        email: str,
    ) -> UserCredentials | None:
        """
        Return the user and stored password hash.

        Return None when the email does not exist.
        """

        raise NotImplementedError

    @abstractmethod
    async def get_user_by_id(
        self,
        user_id: str,
    ) -> User | None:
        """Return a public user by identifier."""

        raise NotImplementedError

    @abstractmethod
    async def create_user(
        self,
        full_name: str,
        email: str,
        hashed_password: str,
    ) -> User:
        """
        Persist a user with a password hash.

        This method must never accept or store a plaintext password.
        """

        raise NotImplementedError
