"""Unit tests for privacy-aware, account-wide online presence."""

from typing import Any

import pytest

from app.domains.presence.application.services import PresenceService
from app.domains.presence.domain.exceptions import (
    PresencePermissionDeniedError,
)
from app.domains.presence.domain.models import OnlineGroupMember
from app.domains.presence.domain.repository import (
    PresenceRepository,
    PresenceStore,
)
from app.domains.presence.infrastructure.redis_store import RedisPresenceStore
from app.domains.study_groups.domain.models import StudyGroupMemberRole


pytestmark = pytest.mark.asyncio


class FakePresenceRepository(PresenceRepository):
    """Small repository substitute for application-service tests."""

    def __init__(self) -> None:
        self.preferences = {"requester": True, "hidden": False}
        self.members = {"requester", "visible", "hidden"}

    async def get_show_online_status(self, user_id: str) -> bool:
        return self.preferences[user_id]

    async def set_show_online_status(
        self,
        *,
        user_id: str,
        enabled: bool,
    ) -> bool:
        self.preferences[user_id] = enabled
        return enabled

    async def is_active_group_member(
        self,
        *,
        group_id: str,
        user_id: str,
    ) -> bool:
        return group_id == "group-1" and user_id in self.members

    async def list_online_group_members(
        self,
        *,
        group_id: str,
        online_user_ids: set[str],
    ) -> list[OnlineGroupMember]:
        if group_id != "group-1" or "visible" not in online_user_ids:
            return []
        return [
            OnlineGroupMember(
                user_id="visible",
                full_name="Visible Student",
                role=StudyGroupMemberRole.MEMBER,
            )
        ]


class FakePresenceStore(PresenceStore):
    """In-memory presence state for application-service tests."""

    def __init__(self) -> None:
        self.online_user_ids: set[str] = set()

    async def mark_online(self, user_id: str) -> None:
        self.online_user_ids.add(user_id)

    async def mark_offline(self, user_id: str) -> None:
        self.online_user_ids.discard(user_id)

    async def list_online_user_ids(self) -> set[str]:
        return set(self.online_user_ids)


class FakeSortedSetRedis:
    """Redis sorted-set subset used by ``RedisPresenceStore``."""

    def __init__(self) -> None:
        self.scores: dict[str, float] = {}

    async def zadd(self, key: str, mapping: dict[str, float]) -> int:
        del key
        self.scores.update(mapping)
        return len(mapping)

    async def zrem(self, key: str, member: str) -> int:
        del key
        return int(self.scores.pop(member, None) is not None)

    async def zremrangebyscore(
        self,
        key: str,
        minimum: Any,
        maximum: float,
    ) -> int:
        del key, minimum
        stale = [
            member
            for member, score in self.scores.items()
            if score <= maximum
        ]
        for member in stale:
            del self.scores[member]
        return len(stale)

    async def zrangebyscore(
        self,
        key: str,
        minimum: float,
        maximum: Any,
    ) -> list[str]:
        del key, maximum
        return [
            member
            for member, score in self.scores.items()
            if score >= minimum
        ]


async def test_heartbeat_obeys_privacy_preference() -> None:
    repository = FakePresenceRepository()
    store = FakePresenceStore()
    service = PresenceService(repository, store)

    assert await service.heartbeat("requester") is True
    assert store.online_user_ids == {"requester"}

    store.online_user_ids.add("hidden")
    assert await service.heartbeat("hidden") is False
    assert store.online_user_ids == {"requester"}


async def test_disabling_visibility_removes_presence_immediately() -> None:
    repository = FakePresenceRepository()
    store = FakePresenceStore()
    store.online_user_ids.add("requester")
    service = PresenceService(repository, store)

    enabled = await service.update_preference(
        user_id="requester",
        enabled=False,
    )

    assert enabled is False
    assert repository.preferences["requester"] is False
    assert store.online_user_ids == set()


async def test_only_group_members_can_view_online_member_list() -> None:
    service = PresenceService(
        FakePresenceRepository(),
        FakePresenceStore(),
    )

    with pytest.raises(PresencePermissionDeniedError):
        await service.list_online_group_members(
            group_id="group-1",
            requester_user_id="outsider",
        )


async def test_group_online_list_uses_temporary_presence() -> None:
    repository = FakePresenceRepository()
    store = FakePresenceStore()
    store.online_user_ids.update({"visible", "unrelated"})
    service = PresenceService(repository, store)

    members = await service.list_online_group_members(
        group_id="group-1",
        requester_user_id="requester",
    )

    assert [member.user_id for member in members] == ["visible"]


async def test_redis_presence_records_removes_and_prunes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    redis = FakeSortedSetRedis()
    store = RedisPresenceStore(redis, ttl_seconds=90)  # type: ignore[arg-type]
    monkeypatch.setattr(
        "app.domains.presence.infrastructure.redis_store.time",
        lambda: 1_000.0,
    )

    redis.scores["stale"] = 900.0
    await store.mark_online("current")
    assert await store.list_online_user_ids() == {"current"}

    await store.mark_offline("current")
    assert await store.list_online_user_ids() == set()
