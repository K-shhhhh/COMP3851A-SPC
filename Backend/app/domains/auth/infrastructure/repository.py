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
