"""Unit tests for Redis authentication adapters without a live Redis server."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from app.api.dependencies import get_auth_service
from app.domains.auth.infrastructure.redis_revocation_store import (
    RedisAccessTokenRevocationStore,
)
from app.domains.auth.infrastructure.redis_ticket_store import (
    RedisWebSocketTicketStore,
)
from app.domains.auth.infrastructure.redis_session_store import (
    RedisRefreshSessionStore,
)
from app.domains.auth.infrastructure.memory_repository import (
    InMemoryAuthRepository,
)


class FakeAsyncRedis:
    """Small Redis substitute that records commands used by these adapters."""

    def __init__(self) -> None:
        self.values: dict[str, Any] = {}
        self.expiries: dict[str, int] = {}

    async def set(
        self,
        key: str,
        value: Any,
        *,
        ex: int,
        nx: bool = False,
    ) -> bool:
        if nx and key in self.values:
            return False

        self.values[key] = value
        self.expiries[key] = ex
        return True

    async def getdel(self, key: str) -> Any | None:
        self.expiries.pop(key, None)
        return self.values.pop(key, None)

    async def get(self, key: str) -> Any | None:
        return self.values.get(key)

    async def delete(self, key: str) -> int:
        self.expiries.pop(key, None)
        return int(self.values.pop(key, None) is not None)

    async def exists(self, key: str) -> int:
        return int(key in self.values)


def test_redis_ticket_is_opaque_expiring_and_single_use() -> None:
    async def scenario() -> None:
        redis = FakeAsyncRedis()
        store = RedisWebSocketTicketStore(redis)  # type: ignore[arg-type]

        ticket = await store.create("student-123", expires_in=60)

        assert ticket not in redis.values
        assert list(redis.expiries.values()) == [60]
        assert await store.consume(ticket) == "student-123"
        assert await store.consume(ticket) is None

    asyncio.run(scenario())


def test_redis_revocation_expires_with_original_access_token() -> None:
    async def scenario() -> None:
        redis = FakeAsyncRedis()
        store = RedisAccessTokenRevocationStore(redis)  # type: ignore[arg-type]
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=60)

        await store.revoke("token-id-123", expires_at)

        assert await store.is_revoked("token-id-123") is True
        assert list(redis.expiries.values()) == [60]

    asyncio.run(scenario())


def test_expired_token_is_not_added_to_redis() -> None:
    async def scenario() -> None:
        redis = FakeAsyncRedis()
        store = RedisAccessTokenRevocationStore(redis)  # type: ignore[arg-type]
        expired_at = datetime.now(timezone.utc) - timedelta(seconds=1)

        await store.revoke("already-expired", expired_at)

        assert redis.values == {}

    asyncio.run(scenario())


def test_redis_refresh_session_is_opaque_touchable_and_revocable() -> None:
    async def scenario() -> None:
        redis = FakeAsyncRedis()
        store = RedisRefreshSessionStore(redis)  # type: ignore[arg-type]

        token = await store.create(
            "student-123",
            idle_timeout_seconds=1800,
            absolute_timeout_seconds=43200,
        )

        assert token not in redis.values
        assert list(redis.expiries.values()) == [1800]
        session = await store.resolve_and_touch(
            token,
            idle_timeout_seconds=1800,
        )
        assert session is not None
        assert session.user_id == "student-123"

        await store.revoke(token)
        assert await store.resolve_and_touch(
            token,
            idle_timeout_seconds=1800,
        ) is None

    asyncio.run(scenario())


def test_auth_service_uses_shared_redis_token_stores() -> None:
    """Runtime authentication state is shared between API workers."""

    service = get_auth_service(
        repository=InMemoryAuthRepository(),
    )

    assert isinstance(
        service.ticket_store,
        RedisWebSocketTicketStore,
    )
    assert isinstance(
        service.revocation_store,
        RedisAccessTokenRevocationStore,
    )
    assert isinstance(service.session_store, RedisRefreshSessionStore)
