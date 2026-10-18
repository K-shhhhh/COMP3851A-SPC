"""In-memory refresh sessions for isolated tests and local adapters."""

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from secrets import token_urlsafe

from app.domains.auth.domain.session_store import (
    RefreshSession,
    RefreshSessionStore,
)


class InMemoryRefreshSessionStore(RefreshSessionStore):
    """Keep hashed opaque sessions inside one Python process."""

    def __init__(self) -> None:
        self._sessions: dict[str, RefreshSession] = {}

    async def create(
        self,
        user_id: str,
        *,
        idle_timeout_seconds: int,
        absolute_timeout_seconds: int,
    ) -> str:
        del idle_timeout_seconds
        token = token_urlsafe(48)
        now = datetime.now(timezone.utc)
        self._sessions[self._key(token)] = RefreshSession(
            user_id=user_id,
            absolute_expires_at=now + timedelta(seconds=absolute_timeout_seconds),
            last_activity_at=now,
        )
        return token

    async def resolve_and_touch(
        self,
        token: str,
        *,
        idle_timeout_seconds: int,
    ) -> RefreshSession | None:
        key = self._key(token)
        session = self._sessions.get(key)
        if session is None:
            return None

        now = datetime.now(timezone.utc)
        if (
            now >= session.absolute_expires_at
            or now - session.last_activity_at
            >= timedelta(seconds=idle_timeout_seconds)
        ):
            self._sessions.pop(key, None)
            return None

        touched = RefreshSession(
            user_id=session.user_id,
            absolute_expires_at=session.absolute_expires_at,
            last_activity_at=now,
        )
        self._sessions[key] = touched
        return touched

    async def revoke(self, token: str) -> None:
        self._sessions.pop(self._key(token), None)

    @staticmethod
    def _key(token: str) -> str:
        return sha256(token.encode("utf-8")).hexdigest()
