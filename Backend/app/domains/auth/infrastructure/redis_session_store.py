"""Redis-backed idle sessions shared by every API process."""

import json
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from math import ceil
from secrets import token_urlsafe

from redis.asyncio import Redis

from app.domains.auth.domain.session_store import (
    RefreshSession,
    RefreshSessionStore,
)


class RedisRefreshSessionStore(RefreshSessionStore):
    """Store only hashes of opaque cookie secrets in Redis."""

    def __init__(
        self,
        redis_client: Redis,
        *,
        key_prefix: str = "spc:auth:session:",
    ) -> None:
        self._redis = redis_client
        self._key_prefix = key_prefix

    async def create(
        self,
        user_id: str,
        *,
        idle_timeout_seconds: int,
        absolute_timeout_seconds: int,
    ) -> str:
        token = token_urlsafe(48)
        now = datetime.now(timezone.utc)
        session = RefreshSession(
            user_id=user_id,
            absolute_expires_at=now + timedelta(seconds=absolute_timeout_seconds),
            last_activity_at=now,
        )
        await self._redis.set(
            self._key(token),
            self._serialize(session),
            ex=min(idle_timeout_seconds, absolute_timeout_seconds),
        )
        return token

    async def resolve_and_touch(
        self,
        token: str,
        *,
        idle_timeout_seconds: int,
    ) -> RefreshSession | None:
        key = self._key(token)
        encoded = await self._redis.get(key)
        if encoded is None:
            return None

        try:
            session = self._deserialize(encoded)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            await self._redis.delete(key)
            return None

        now = datetime.now(timezone.utc)
        if (
            now >= session.absolute_expires_at
            or now - session.last_activity_at
            >= timedelta(seconds=idle_timeout_seconds)
        ):
            await self._redis.delete(key)
            return None

        touched = RefreshSession(
            user_id=session.user_id,
            absolute_expires_at=session.absolute_expires_at,
            last_activity_at=now,
        )
        ttl = min(
            idle_timeout_seconds,
            ceil((session.absolute_expires_at - now).total_seconds()),
        )
        if ttl <= 0:
            await self._redis.delete(key)
            return None

        await self._redis.set(key, self._serialize(touched), ex=ttl)
        return touched

    async def revoke(self, token: str) -> None:
        await self._redis.delete(self._key(token))

    def _key(self, token: str) -> str:
        digest = sha256(token.encode("utf-8")).hexdigest()
        return f"{self._key_prefix}{digest}"

    @staticmethod
    def _serialize(session: RefreshSession) -> str:
        return json.dumps(
            {
                "user_id": session.user_id,
                "absolute_expires_at": session.absolute_expires_at.isoformat(),
                "last_activity_at": session.last_activity_at.isoformat(),
            },
            separators=(",", ":"),
        )

    @staticmethod
    def _deserialize(value: str | bytes) -> RefreshSession:
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        payload = json.loads(value)
        return RefreshSession(
            user_id=payload["user_id"],
            absolute_expires_at=datetime.fromisoformat(
                payload["absolute_expires_at"]
            ),
            last_activity_at=datetime.fromisoformat(payload["last_activity_at"]),
        )
