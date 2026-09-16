"""Redis-backed storage for revoked JWT access-token identifiers."""

from datetime import datetime, timezone
from hashlib import sha256
from math import ceil

from redis.asyncio import Redis

from app.domains.auth.domain.revocation_store import (
    AccessTokenRevocationStore,
)


class RedisAccessTokenRevocationStore(AccessTokenRevocationStore):
    """Share logout revocations across all backend processes."""

    def __init__(
        self,
        redis_client: Redis,
        *,
        key_prefix: str = "spc:auth:revoked-token:",
    ) -> None:
        self._redis = redis_client
        self._key_prefix = key_prefix

    async def revoke(
        self,
        token_id: str,
        expires_at: datetime,
    ) -> None:
        """Store a revoked token only for the remainder of its signed lifetime."""

        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        seconds_remaining = ceil(
            (expires_at - datetime.now(timezone.utc)).total_seconds()
        )
        if seconds_remaining <= 0:
            return

        await self._redis.set(
            self._revocation_key(token_id),
            "1",
            ex=seconds_remaining,
        )

    async def is_revoked(self, token_id: str) -> bool:
        """Return whether a logout marker still exists for the token."""

        return bool(await self._redis.exists(self._revocation_key(token_id)))

    def _revocation_key(self, token_id: str) -> str:
        token_digest = sha256(token_id.encode("utf-8")).hexdigest()
        return f"{self._key_prefix}{token_digest}"
