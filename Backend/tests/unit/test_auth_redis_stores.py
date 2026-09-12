"""Unit tests for Redis authentication adapters without a live Redis server."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from app.api.dependencies import get_auth_service
from app.domains.auth.infrastructure.memory_revocation_store import (
    InMemoryAccessTokenRevocationStore,
)
from app.domains.auth.infrastructure.memory_ticket_store import (
    InMemoryWebSocketTicketStore,
)
from app.domains.auth.infrastructure.redis_revocation_store import (
    RedisAccessTokenRevocationStore,
)
from app.domains.auth.infrastructure.redis_ticket_store import (
    RedisWebSocketTicketStore,
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


def test_dependency_injection_still_uses_local_memory_stores() -> None:
    service = get_auth_service()

    assert isinstance(service.ticket_store, InMemoryWebSocketTicketStore)
    assert isinstance(
        service.revocation_store,
        InMemoryAccessTokenRevocationStore,
    )
