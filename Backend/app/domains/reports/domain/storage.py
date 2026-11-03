"""Private storage contract for user-submitted report evidence."""

from abc import ABC, abstractmethod


class EvidenceStorageError(Exception):
    """Raised when private evidence cannot be stored or retrieved safely."""


class EvidenceStorage(ABC):
    @abstractmethod
    async def store_evidence(self, key: str, data: bytes) -> None:
        """Store evidence bytes under a backend-generated private key."""

        raise NotImplementedError

    @abstractmethod
    async def read_evidence(self, key: str) -> bytes:
        """Read evidence bytes after validating the private key."""

        raise NotImplementedError

    @abstractmethod
    async def delete_evidence(self, key: str) -> bool:
        """Delete evidence bytes when present."""

        raise NotImplementedError
