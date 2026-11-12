"""Private local-file storage for uploaded PDF attachments."""

import asyncio
import os
from pathlib import Path
from uuid import uuid4

from app.domains.notes.domain.exceptions import AttachmentStorageError
from app.domains.notes.domain.storage import AttachmentStorage


class LocalAttachmentStorage(AttachmentStorage):
    """Store PDFs under personal/ and groups/ subdirectories."""

    def __init__(self, root_directory: str | Path) -> None:
        self._root_directory = Path(root_directory).expanduser().resolve()

        try:
            self._root_directory.mkdir(parents=True, exist_ok=True)
            self._root_directory.chmod(0o750)
            for sub in ("personal", "groups"):
                subdir = self._root_directory / sub
                subdir.mkdir(parents=True, exist_ok=True)
                subdir.chmod(0o750)
        except OSError as exc:
            raise AttachmentStorageError(
                "The attachment storage directory could not be initialized."
            ) from exc

    async def store_pdf(self, data: bytes, subcategory: str = "personal") -> str:
        if not data:
            raise AttachmentStorageError(
                "Empty attachment content cannot be stored."
            )

        if subcategory not in {"personal", "groups"}:
            raise AttachmentStorageError(
                "The attachment storage subcategory is invalid."
            )

        target_dir = self._root_directory / subcategory
        storage_identifier = uuid4().hex
        destination = target_dir / f"{storage_identifier}.pdf"
        temporary = target_dir / f".{storage_identifier}.tmp"

        try:
            await asyncio.to_thread(temporary.write_bytes, data)
            await asyncio.to_thread(temporary.chmod, 0o640)
            await asyncio.to_thread(os.replace, temporary, destination)
        except OSError as exc:
            await self._remove_temporary_file(temporary)
            raise AttachmentStorageError(
                "The uploaded attachment could not be stored."
            ) from exc

        return str(destination)

    async def read_pdf(self, object_path: str) -> bytes:
        safe_path = self._resolve_safe_pdf_path(object_path)

        try:
            return await asyncio.to_thread(safe_path.read_bytes)
        except OSError as exc:
            raise AttachmentStorageError(
                "The stored attachment could not be read."
            ) from exc

    async def delete_pdf(self, object_path: str) -> bool:
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
        candidate = Path(object_path).expanduser().resolve()

        allowed_parents = {
            self._root_directory,
            self._root_directory / "personal",
            self._root_directory / "groups",
        }
        if candidate.parent not in allowed_parents:
            raise AttachmentStorageError(
                "The attachment object path is outside private storage."
            )

        if candidate.suffix.lower() != ".pdf":
            raise AttachmentStorageError(
                "The attachment object path is not a PDF."
            )

        return candidate

    async def _remove_temporary_file(self, path: Path) -> None:
        try:
            await asyncio.to_thread(path.unlink, missing_ok=True)
        except OSError:
            pass
