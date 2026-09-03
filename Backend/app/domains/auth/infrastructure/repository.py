# DEMO auth repository: returns constructed objects instead of executing SQL.
# Do not interpret successful responses as persisted data or authenticated access.
from app.domains.auth.domain.models import AuthToken, User
from app.domains.auth.domain.repository import AuthRepository


class PostgreSQLAuthRepository(AuthRepository):
    """
    Placeholder repository implementation.

    Later this class will communicate with PostgreSQL.
    """

    async def login(
        self,
        email: str,
        password: str,
    ) -> AuthToken:

        # Placeholder implementation
        return AuthToken(
            access_token="demo-access-token",
        )

    async def register(
        self,
        full_name: str,
        email: str,
        password: str,
    ) -> User:

        # Placeholder implementation
        return User(
            id=1,
            full_name=full_name,
            email=email,
        )
