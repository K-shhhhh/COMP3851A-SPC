"""Private local-file storage for report evidence."""

import asyncio
import os
from pathlib import Path

from app.domains.reports.domain.storage import (
    EvidenceStorage,
    EvidenceStorageError,
)


class LocalEvidenceStorage(EvidenceStorage):
    """Store evidence below one configured, non-public directory."""

    def __init__(self, root_directory: str | Path) -> None:
        self._root_directory = Path(root_directory).expanduser().resolve()
        try:
            self._root_directory.mkdir(parents=True, exist_ok=True)
            self._root_directory.chmod(0o700)
        except OSError as exc:
            raise EvidenceStorageError(
                "The evidence storage directory could not be initialized."
            ) from exc

    async def store_evidence(self, key: str, data: bytes) -> None:
        if not data:
            raise EvidenceStorageError("Empty evidence cannot be stored.")
        destination = self._resolve_key(key)
        temporary = destination.with_name(f".{destination.name}.tmp")
        try:
            await asyncio.to_thread(destination.parent.mkdir, parents=True, exist_ok=True)
            await asyncio.to_thread(destination.parent.chmod, 0o700)
            await asyncio.to_thread(destination.parent.parent.chmod, 0o700)
            await asyncio.to_thread(temporary.write_bytes, data)
            await asyncio.to_thread(temporary.chmod, 0o600)
            await asyncio.to_thread(os.replace, temporary, destination)
        except OSError as exc:
            await self._remove_temporary(temporary)
            raise EvidenceStorageError("Evidence could not be stored.") from exc

    async def read_evidence(self, key: str) -> bytes:
        path = self._resolve_key(key)
        try:
            return await asyncio.to_thread(path.read_bytes)
        except OSError as exc:
            raise EvidenceStorageError("Evidence could not be read.") from exc

    async def delete_evidence(self, key: str) -> bool:
        path = self._resolve_key(key)
        if not path.exists():
            return False
        try:
            await asyncio.to_thread(path.unlink)
            return True
        except OSError as exc:
            raise EvidenceStorageError("Evidence could not be deleted.") from exc

    def _resolve_key(self, key: str) -> Path:
        if not key or Path(key).is_absolute():
            raise EvidenceStorageError("The evidence storage key is invalid.")
        candidate = (self._root_directory / key).resolve()
        if self._root_directory not in candidate.parents:
            raise EvidenceStorageError("The evidence key is outside private storage.")
        return candidate

    @staticmethod
    async def _remove_temporary(path: Path) -> None:
        try:
            await asyncio.to_thread(path.unlink, missing_ok=True)
        except OSError:
            pass
