"""Storage contract for revoked JWT access-token identifiers."""

from abc import ABC, abstractmethod
from datetime import datetime


class AccessTokenRevocationStore(ABC):
    """Track revoked tokens only until their original expiry time."""

    @abstractmethod
    async def revoke(
        self,
        token_id: str,
        expires_at: datetime,
    ) -> None:
        """Revoke one token until its signed expiry time."""

        raise NotImplementedError

    @abstractmethod
    async def is_revoked(self, token_id: str) -> bool:
        """Return whether the token is currently revoked."""

        raise NotImplementedError
