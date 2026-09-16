"""Storage contract for private learning-material files."""

from abc import ABC, abstractmethod


class AttachmentStorage(ABC):
    """Define private storage operations for uploaded PDFs."""

    @abstractmethod
    async def store_pdf(self, data: bytes) -> str:
        """Persist PDF bytes and return a trusted private object path."""

        raise NotImplementedError

    @abstractmethod
    async def read_pdf(self, object_path: str) -> bytes:
        """Read a PDF for trusted internal processing."""

        raise NotImplementedError

    @abstractmethod
    async def delete_pdf(self, object_path: str) -> bool:
        """Delete a privately stored PDF when it exists."""

        raise NotImplementedError
