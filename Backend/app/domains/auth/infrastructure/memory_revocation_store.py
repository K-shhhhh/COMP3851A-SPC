"""
Temporary in-memory access-token revocation storage.

This works for one local backend process. Hetzner staging and production must
replace it with Redis so revocations are shared across backend instances.
"""

from datetime import datetime, timezone

from app.domains.auth.domain.revocation_store import (
    AccessTokenRevocationStore,
)


class InMemoryAccessTokenRevocationStore(AccessTokenRevocationStore):
    """Keep revoked token IDs in local memory until they expire."""

    def __init__(self) -> None:
        self._revoked_tokens: dict[str, datetime] = {}

    async def revoke(
        self,
        token_id: str,
        expires_at: datetime,
    ) -> None:
        self._remove_expired_entries()
        self._revoked_tokens[token_id] = expires_at

    async def is_revoked(self, token_id: str) -> bool:
        self._remove_expired_entries()
        return token_id in self._revoked_tokens

    def _remove_expired_entries(self) -> None:
        now = datetime.now(timezone.utc)
        expired_ids = [
            token_id
            for token_id, expires_at in self._revoked_tokens.items()
            if expires_at <= now
        ]

        for token_id in expired_ids:
            self._revoked_tokens.pop(token_id, None)
