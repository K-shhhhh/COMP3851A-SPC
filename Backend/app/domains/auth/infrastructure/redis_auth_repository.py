"""Redis-backed authentication repository.

Same reasoning as the notes/chats Redis repositories: InMemoryAuthRepository
stores accounts in a plain Python dict, which is wiped every time the
backend process restarts. This implements the exact same AuthRepository
interface, backed by Redis instead, so registered accounts (and the
attachments/chunks they own) survive restarts and stay linked to the same
user identity.

Throwaway once the real PostgreSQL authentication repository lands.
"""

import json
from datetime import datetime, timezone
from uuid import uuid4

from redis.asyncio import Redis

from app.domains.auth.domain.models import User, UserCredentials
from app.domains.auth.domain.repository import AuthRepository


class RedisAuthRepository(AuthRepository):
    """Store user accounts and credentials in Redis instead of process memory."""

    def __init__(
        self,
        redis_client: Redis,
        *,
        key_prefix: str = "spc:auth:",
    ) -> None:
        self._redis = redis_client
        self._key_prefix = key_prefix

    def _user_key(self, user_id: str) -> str:
        return f"{self._key_prefix}user:{user_id}"

    def _email_index_key(self, email: str) -> str:
        return f"{self._key_prefix}email_index:{email}"

    # ---- serialization -----------------------------------------------
    # User and UserCredentials are both frozen dataclasses, not directly
    # JSON-serializable (created_at is a datetime, needs converting).

    def _serialize(self, credentials: UserCredentials) -> str:
        data = {
            "id": credentials.user.id,
            "full_name": credentials.user.full_name,
            "email": credentials.user.email,
            "role": credentials.user.role,
            "is_active": credentials.user.is_active,
            "created_at": credentials.user.created_at.isoformat(),
            "hashed_password": credentials.hashed_password,
        }
        return json.dumps(data)

    def _deserialize(self, raw: str) -> UserCredentials:
        data = json.loads(raw)
        user = User(
            id=data["id"],
            full_name=data["full_name"],
            email=data["email"],
            role=data["role"],
            is_active=data["is_active"],
            created_at=datetime.fromisoformat(data["created_at"]),
        )
        return UserCredentials(user=user, hashed_password=data["hashed_password"])

    # ---- interface methods --------------------------------------------

    async def get_credentials_by_email(
        self,
        email: str,
    ) -> UserCredentials | None:
        """Return credentials for login, or None if the email is unknown."""

        user_id = await self._redis.get(self._email_index_key(email))

        if user_id is None:
            return None

        raw = await self._redis.get(self._user_key(user_id))

        if raw is None:
            return None

        return self._deserialize(raw)

    async def get_user_by_id(
        self,
        user_id: str,
    ) -> User | None:
        """Return a public user record for /auth/me and similar lookups."""

        raw = await self._redis.get(self._user_key(user_id))

        if raw is None:
            return None

        credentials = self._deserialize(raw)

        return credentials.user

    async def create_user(
        self,
        full_name: str,
        email: str,
        hashed_password: str,
    ) -> User:
        """Persist a new user with a fresh UUID identifier.

        Duplicate-email checking happens in the application/service layer
        above this repository (it calls get_credentials_by_email first),
        matching the in-memory adapter's own division of responsibility.
        """

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

        await self._redis.set(self._user_key(user.id), self._serialize(credentials))
        await self._redis.set(self._email_index_key(email), user.id)

        return user
