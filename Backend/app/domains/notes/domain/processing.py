"""Boundary between note uploads and background document processing."""

from abc import ABC, abstractmethod


class AttachmentProcessingDispatcher(ABC):
    """Request processing without exposing Celery to the Notes service."""

    @abstractmethod
    async def dispatch(
        self,
        *,
        attachment_id: int,
        object_path: str,
    ) -> None:
        """Request extraction, chunking, and embedding for an attachment."""

        raise NotImplementedError
