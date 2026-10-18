"""Redis implementation of temporary account-wide online presence."""

from time import time

from redis.asyncio import Redis

from app.domains.presence.domain.repository import PresenceStore


class RedisPresenceStore(PresenceStore):
    """Track the latest authenticated heartbeat for each visible user."""

    def __init__(
        self,
        redis_client: Redis,
        *,
        ttl_seconds: int,
        key: str = "spc:presence:online-users",
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")

        self._redis = redis_client
        self._ttl_seconds = ttl_seconds
        self._key = key

    async def mark_online(self, user_id: str) -> None:
        """Record the latest heartbeat timestamp for the user."""

        await self._redis.zadd(
            self._key,
            {user_id: time()},
        )

    async def mark_offline(self, user_id: str) -> None:
        """Remove the user from the online-presence index."""

        await self._redis.zrem(self._key, user_id)

    async def list_online_user_ids(self) -> set[str]:
        """Return users with a heartbeat inside the configured TTL."""

        cutoff = time() - self._ttl_seconds

        # Opportunistically remove stale entries whenever presence is read.
        await self._redis.zremrangebyscore(
            self._key,
            "-inf",
            cutoff,
        )

        values = await self._redis.zrangebyscore(
            self._key,
            cutoff,
            "+inf",
        )

        return {
            value.decode("utf-8") if isinstance(value, bytes) else value
            for value in values
        }
