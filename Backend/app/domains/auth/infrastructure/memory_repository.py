"""
Temporary in-memory authentication repository.

Use this only for local endpoint testing while PostgreSQL authentication is
being developed. Users disappear whenever the backend process restarts.
Never select this repository in staging or production.
"""

from datetime import datetime, timezone
from uuid import uuid4

from app.domains.auth.domain.models import User, UserCredentials
from app.domains.auth.domain.repository import AuthRepository


class InMemoryAuthRepository(AuthRepository):
    """Store temporary authentication records inside one Python process."""

    def __init__(self) -> None:
        """Initialize empty indexes for email and identifier lookups."""

        # Index by normalized email for login and duplicate detection.
        self._users_by_email: dict[str, UserCredentials] = {}

        # Index public users by ID for get_current_user.
        self._users_by_id: dict[str, User] = {}

    async def get_credentials_by_email(
        self,
        email: str,
    ) -> UserCredentials | None:
        """Return credentials matching a normalized email address."""

        return self._users_by_email.get(email)

    async def get_user_by_id(
        self,
        user_id: str,
    ) -> User | None:
        """Return a public user record by identifier."""

        return self._users_by_id.get(user_id)

    async def create_user(
        self,
        full_name: str,
        email: str,
        hashed_password: str,
    ) -> User:
        """Create a temporary student account containing only a password hash."""

        user = User(
            id=str(uuid4()),
            full_name=full_name,
            email=email,
            role="student",
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )

        credentials = UserCredentials(
            user=user,
            hashed_password=hashed_password,
        )

        self._users_by_email[email] = credentials
        self._users_by_id[user.id] = user

        return user
