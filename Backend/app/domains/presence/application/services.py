"""Application use cases for privacy-aware account-wide presence."""

from app.domains.presence.domain.exceptions import (
    PresencePermissionDeniedError,
)
from app.domains.presence.domain.models import OnlineGroupMember
from app.domains.presence.domain.repository import (
    PresenceRepository,
    PresenceStore,
)


class PresenceService:
    """Coordinate persistent privacy preferences and temporary presence."""

    def __init__(
        self,
        repository: PresenceRepository,
        store: PresenceStore,
    ) -> None:
        self._repository = repository
        self._store = store

    async def heartbeat(self, user_id: str) -> bool:
        """Mark a visible authenticated user online.

        This operation intentionally does not refresh the authentication session.
        Automatic presence heartbeats must never prevent the authentication
        inactivity timeout.
        """

        enabled = await self._repository.get_show_online_status(user_id)

        if not enabled:
            await self._store.mark_offline(user_id)
            return False

        await self._store.mark_online(user_id)
        return True

    async def mark_offline(self, user_id: str) -> None:
        """Remove the user's temporary presence immediately."""

        await self._store.mark_offline(user_id)

    async def get_preference(self, user_id: str) -> bool:
        """Return whether the user allows online_status visibility."""

        return await self._repository.get_show_online_status(user_id)

    async def update_preference(
        self,
        *,
        user_id: str,
        enabled: bool,
    ) -> bool:
        """Persist the privacy setting and update temporary presence."""

        updated = await self._repository.set_show_online_status(
            user_id=user_id,
            enabled=enabled,
        )

        if updated:
            await self._store.mark_online(user_id)
        else:
            await self._store.mark_offline(user_id)

        return updated

    async def list_online_group_members(
        self,
        *,
        group_id: str,
        requester_user_id: str,
    ) -> list[OnlineGroupMember]:
        """Return online members only to another active group member."""

        is_member = await self._repository.is_active_group_member(
            group_id=group_id,
            user_id=requester_user_id,
        )

        if not is_member:
            raise PresencePermissionDeniedError(
                "You must be a group member to view online members."
            )

        online_user_ids = await self._store.list_online_user_ids()

        return await self._repository.list_online_group_members(
            group_id=group_id,
            online_user_ids=online_user_ids,
        )
