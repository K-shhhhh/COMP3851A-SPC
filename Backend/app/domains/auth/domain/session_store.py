"""Storage contract for opaque, server-managed browser sessions."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class RefreshSession:
    """A valid browser session resolved from an opaque cookie secret."""

    user_id: str
    absolute_expires_at: datetime
    last_activity_at: datetime


class RefreshSessionStore(ABC):
    """Create, touch, and revoke idle-expiring browser sessions."""

    @abstractmethod
    async def create(
        self,
        user_id: str,
        *,
        idle_timeout_seconds: int,
        absolute_timeout_seconds: int,
    ) -> str:
        """Create a session and return its unguessable cookie value."""

        raise NotImplementedError

    @abstractmethod
    async def resolve_and_touch(
        self,
        token: str,
        *,
        idle_timeout_seconds: int,
    ) -> RefreshSession | None:
        """Resolve an active session and record authenticated activity."""

        raise NotImplementedError

    @abstractmethod
    async def revoke(self, token: str) -> None:
        """Revoke a browser session represented by an opaque cookie."""

        raise NotImplementedError
