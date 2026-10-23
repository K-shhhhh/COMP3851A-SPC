"""Database and private-storage contract for user reports."""

from abc import ABC, abstractmethod

from app.domains.reports.domain.models import (
    EvidenceUpload,
    Report,
    ReportCategory,
    ReportPage,
    ReportStatus,
    ReportTargetType,
)


class ReportRepository(ABC):
    """Persist reports while enforcing target access and immutable snapshots."""

    @abstractmethod
    async def create_report(
        self,
        *,
        reporter_user_id: str,
        target_type: ReportTargetType,
        target_id: str,
        category: ReportCategory,
        description: str,
        include_limited_context: bool,
        evidence: list[EvidenceUpload],
    ) -> Report:
        """Validate access and atomically create a server-side target snapshot.

        Message reports must snapshot the selected message. Limited context may
        include only a small bounded window when explicitly requested; never
        copy an entire private conversation. Evidence must use private storage.
        """

        raise NotImplementedError

    @abstractmethod
    async def list_reports(
        self,
        *,
        reporter_user_id: str,
        status: ReportStatus | None,
        cursor: str | None,
        limit: int,
    ) -> ReportPage:
        """List only reports submitted by the authenticated user."""

        raise NotImplementedError

    @abstractmethod
    async def get_report(
        self,
        *,
        reporter_user_id: str,
        report_id: str,
    ) -> Report | None:
        """Return a report only when it belongs to the authenticated user."""

        raise NotImplementedError
