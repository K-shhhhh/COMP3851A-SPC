"""Storage contracts required by account-wide presence use cases."""

from abc import ABC, abstractmethod

from app.domains.presence.domain.models import OnlineGroupMember


class PresenceRepository(ABC):
    """Persist privacy preferences and read authorized group profiles."""

    @abstractmethod
    async def get_show_online_status(self, user_id: str) -> bool:
        """Return the user's persisted online-status preference."""

        raise NotImplementedError

    @abstractmethod
    async def set_show_online_status(
        self,
        *,
        user_id: str,
        enabled: bool,
    ) -> bool:
        """Update and return the user's online-status preference."""

        raise NotImplementedError

    @abstractmethod
    async def is_active_group_member(
        self,
        *,
        group_id: str,
        user_id: str,
    ) -> bool:
        """Check whether the user may view presence for this group."""

        raise NotImplementedError

    @abstractmethod
    async def list_online_group_members(
        self,
        *,
        group_id: str,
        online_user_ids: set[str],
    ) -> list[OnlineGroupMember]:
        """Return safe profiles for online, visible members of the group."""

        raise NotImplementedError


class PresenceStore(ABC):
    """Manage short-lived presence timestamps outside PostgreSQL."""

    @abstractmethod
    async def mark_online(self, user_id: str) -> None:
        """Record a current authenticated heartbeat."""

        raise NotImplementedError

    @abstractmethod
    async def mark_offline(self, user_id: str) -> None:
        """Remove the user's current presence immediately."""

        raise NotImplementedError

    @abstractmethod
    async def list_online_user_ids(self) -> set[str]:
        """Return users whose latest heartbeat remains recent."""

        raise NotImplementedError
