"""Temporary local dispatcher for document-processing requests.

This adapter records the handoff during local endpoint development. Krish's
Celery adapter will replace it when the processing pipeline is merged.
"""

import asyncio

from app.domains.notes.domain.processing import (
    AttachmentProcessingDispatcher,
)


class InMemoryAttachmentProcessingDispatcher(
    AttachmentProcessingDispatcher
):
    """Record processing requests without running the RAG pipeline."""

    def __init__(self) -> None:
        """Initialize an empty list of dispatched attachment identifiers."""

        self._requests: list[tuple[int, str]] = []
        self._lock = asyncio.Lock()

    @property
    def requests(self) -> tuple[tuple[int, str], ...]:
        """Return an immutable snapshot for local tests and inspection."""

        return tuple(self._requests)

    async def dispatch(
        self,
        *,
        attachment_id: int,
        object_path: str,
    ) -> None:
        """Record the exact handoff expected by the processing adapter."""

        async with self._lock:
            self._requests.append((attachment_id, object_path))
