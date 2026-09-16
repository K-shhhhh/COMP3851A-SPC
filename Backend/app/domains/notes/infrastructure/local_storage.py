"""Private local-file storage for uploaded PDF attachments."""

import asyncio
import os
from pathlib import Path
from uuid import uuid4

from app.domains.notes.domain.exceptions import AttachmentStorageError
from app.domains.notes.domain.storage import AttachmentStorage


class LocalAttachmentStorage(AttachmentStorage):
    """Store PDFs under one configured private directory."""

    def __init__(self, root_directory: str | Path) -> None:
        """Initialize the private storage directory."""

        self._root_directory = Path(root_directory).expanduser().resolve()

        try:
            self._root_directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise AttachmentStorageError(
                "The attachment storage directory could not be initialized."
            ) from exc

    async def store_pdf(self, data: bytes) -> str:
        """Atomically store content under a backend-generated PDF name."""

        if not data:
            raise AttachmentStorageError(
                "Empty attachment content cannot be stored."
            )

        storage_identifier = uuid4().hex
        destination = self._root_directory / f"{storage_identifier}.pdf"
        temporary = self._root_directory / f".{storage_identifier}.tmp"

        try:
            await asyncio.to_thread(temporary.write_bytes, data)
            await asyncio.to_thread(os.replace, temporary, destination)
        except OSError as exc:
            await self._remove_temporary_file(temporary)
            raise AttachmentStorageError(
                "The uploaded attachment could not be stored."
            ) from exc

        return str(destination)

    async def read_pdf(self, object_path: str) -> bytes:
        """Read a PDF after validating that it belongs to this storage."""

        safe_path = self._resolve_safe_pdf_path(object_path)

        try:
            return await asyncio.to_thread(safe_path.read_bytes)
        except OSError as exc:
            raise AttachmentStorageError(
                "The stored attachment could not be read."
            ) from exc

    async def delete_pdf(self, object_path: str) -> bool:
        """Delete a PDF after validating its private storage path."""

        safe_path = self._resolve_safe_pdf_path(object_path)

        if not safe_path.exists():
            return False

        try:
            await asyncio.to_thread(safe_path.unlink)
        except OSError as exc:
            raise AttachmentStorageError(
                "The stored attachment could not be deleted."
            ) from exc

        return True

    def _resolve_safe_pdf_path(self, object_path: str) -> Path:
        """Prevent reads and deletions outside the configured directory."""

        candidate = Path(object_path).expanduser().resolve()

        if candidate.parent != self._root_directory:
            raise AttachmentStorageError(
                "The attachment object path is outside private storage."
            )

        if candidate.suffix.lower() != ".pdf":
            raise AttachmentStorageError(
                "The attachment object path is not a PDF."
            )

        return candidate

    async def _remove_temporary_file(self, path: Path) -> None:
        """Best-effort removal for a partially written upload."""

        try:
            await asyncio.to_thread(path.unlink, missing_ok=True)
        except OSError:
            pass
