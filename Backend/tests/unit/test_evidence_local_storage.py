"""Security and lifecycle tests for private report-evidence storage."""

from pathlib import Path

import pytest

from app.domains.reports.domain.storage import EvidenceStorageError
from app.domains.reports.infrastructure.local_storage import LocalEvidenceStorage


pytestmark = pytest.mark.asyncio


async def test_evidence_round_trip_and_delete(tmp_path: Path) -> None:
    storage = LocalEvidenceStorage(tmp_path / "evidence")
    key = "reports/report-1/evidence/proof.png"

    await storage.store_evidence(key, b"proof-bytes")

    assert await storage.read_evidence(key) == b"proof-bytes"
    assert (tmp_path / "evidence" / key).stat().st_mode & 0o777 == 0o600
    assert await storage.delete_evidence(key) is True
    assert await storage.delete_evidence(key) is False


@pytest.mark.parametrize(
    "unsafe_key",
    ("../private.png", "/tmp/private.png", "reports/../../private.png", ""),
)
async def test_evidence_storage_rejects_keys_outside_root(
    tmp_path: Path,
    unsafe_key: str,
) -> None:
    storage = LocalEvidenceStorage(tmp_path / "evidence")

    with pytest.raises(EvidenceStorageError):
        await storage.store_evidence(unsafe_key, b"proof-bytes")


async def test_evidence_storage_rejects_empty_content(tmp_path: Path) -> None:
    storage = LocalEvidenceStorage(tmp_path / "evidence")

    with pytest.raises(EvidenceStorageError, match="Empty evidence"):
        await storage.store_evidence("reports/report-1/empty.png", b"")
