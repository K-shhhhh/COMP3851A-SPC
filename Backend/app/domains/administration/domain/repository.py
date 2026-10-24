"""Persistence contract for administration use cases.

The database adapter must apply every governance mutation and its audit entry
in one transaction. Implementations must return only sanitized operational
messages and must never expose passwords, tokens, raw evidence, or complete
chat histories.
"""

from abc import ABC, abstractmethod
from datetime import datetime

from app.domains.administration.domain.models import (
    AdminAttachmentDetails,
    AdminAttachmentPage,
    AdminEvidenceFile,
    AdminGroupDetails,
    AdminGroupPage,
    AdminReportDetails,
    AdminReportGovernanceAction,
    AdminReportPage,
    AdminReportResolutionOutcome,
    AdminUserDetails,
    AdminUserPage,
    AdministrationActor,
    AdministrationAttachmentSource,
    AdministrationAttachmentStatus,
    AdministrationGroupStatus,
    AdministrationGroupVisibility,
    AdministrationLogSeverity,
    AdministrationUserRole,
    AdministrationUserStatus,
    DashboardSnapshot,
    GovernanceActionResult,
    SystemLogEntry,
    SystemLogPage,
    SystemStatus,
)
from app.domains.reports.domain.models import ReportStatus, ReportTargetType


class AdministrationRepository(ABC):
    @abstractmethod
    async def get_system_status(self) -> SystemStatus:
        raise NotImplementedError

    @abstractmethod
    async def get_dashboard(self) -> DashboardSnapshot:
        raise NotImplementedError

    @abstractmethod
    async def list_users(
        self,
        *,
        search: str | None,
        status: AdministrationUserStatus | None,
        role: AdministrationUserRole | None,
        cursor: str | None,
        limit: int,
    ) -> AdminUserPage:
        raise NotImplementedError

    @abstractmethod
    async def get_user(self, user_id: str) -> AdminUserDetails | None:
        raise NotImplementedError

    @abstractmethod
    async def count_active_administrators(self) -> int:
        raise NotImplementedError

    @abstractmethod
    async def deactivate_user(
        self,
        *,
        user_id: str,
        actor: AdministrationActor,
    ) -> GovernanceActionResult | None:
        """Deactivate a user and append an audit event atomically."""

        raise NotImplementedError

    @abstractmethod
    async def reactivate_user(
        self,
        *,
        user_id: str,
        actor: AdministrationActor,
    ) -> GovernanceActionResult | None:
        """Reactivate a user and append an audit event atomically."""

        raise NotImplementedError

    @abstractmethod
    async def list_groups(
        self,
        *,
        search: str | None,
        visibility: AdministrationGroupVisibility | None,
        status: AdministrationGroupStatus | None,
        cursor: str | None,
        limit: int,
    ) -> AdminGroupPage:
        raise NotImplementedError

    @abstractmethod
    async def get_group(self, group_id: str) -> AdminGroupDetails | None:
        raise NotImplementedError

    @abstractmethod
    async def remove_group(
        self,
        *,
        group_id: str,
        actor: AdministrationActor,
    ) -> GovernanceActionResult | None:
        """Soft-remove a non-personal group and audit the action atomically."""

        raise NotImplementedError

    @abstractmethod
    async def restore_group(
        self,
        *,
        group_id: str,
        actor: AdministrationActor,
    ) -> GovernanceActionResult | None:
        raise NotImplementedError

    @abstractmethod
    async def list_attachments(
        self,
        *,
        search: str | None,
        status: AdministrationAttachmentStatus | None,
        source: AdministrationAttachmentSource | None,
        include_removed: bool,
        cursor: str | None,
        limit: int,
    ) -> AdminAttachmentPage:
        raise NotImplementedError

    @abstractmethod
    async def get_attachment(
        self,
        attachment_id: int,
    ) -> AdminAttachmentDetails | None:
        raise NotImplementedError

    @abstractmethod
    async def remove_attachment(
        self,
        *,
        attachment_id: int,
        actor: AdministrationActor,
    ) -> GovernanceActionResult | None:
        """Soft-remove metadata, delete private content, and audit atomically."""

        raise NotImplementedError

    @abstractmethod
    async def retry_attachment(
        self,
        *,
        attachment_id: int,
        actor: AdministrationActor,
    ) -> GovernanceActionResult | None:
        """Reset a failed attachment and enqueue processing exactly once."""

        raise NotImplementedError

    @abstractmethod
    async def list_system_logs(
        self,
        *,
        severity: AdministrationLogSeverity | None,
        service: str | None,
        request_id: str | None,
        occurred_from: datetime | None,
        occurred_to: datetime | None,
        cursor: str | None,
        limit: int,
    ) -> SystemLogPage:
        raise NotImplementedError

    @abstractmethod
    async def get_system_log(self, event_id: str) -> SystemLogEntry | None:
        raise NotImplementedError

    @abstractmethod
    async def list_reports(
        self,
        *,
        search: str | None,
        status: ReportStatus | None,
        target_type: ReportTargetType | None,
        cursor: str | None,
        limit: int,
    ) -> AdminReportPage:
        raise NotImplementedError

    @abstractmethod
    async def get_report(self, report_id: str) -> AdminReportDetails | None:
        """Return report-preserved context only, never an unrestricted chat."""

        raise NotImplementedError

    @abstractmethod
    async def start_report_review(
        self, *, report_id: str, actor: AdministrationActor
    ) -> AdminReportDetails | None:
        raise NotImplementedError

    @abstractmethod
    async def add_report_note(
        self, *, report_id: str, administrator_user_id: str, note: str
    ) -> AdminReportDetails | None:
        raise NotImplementedError

    @abstractmethod
    async def resolve_report(
        self,
        *,
        report_id: str,
        administrator_user_id: str,
        outcome: AdminReportResolutionOutcome,
        internal_reason: str,
        public_summary: str,
    ) -> AdminReportDetails | None:
        raise NotImplementedError

    @abstractmethod
    async def dismiss_report(
        self,
        *,
        report_id: str,
        administrator_user_id: str,
        internal_reason: str,
        public_summary: str,
    ) -> AdminReportDetails | None:
        raise NotImplementedError

    @abstractmethod
    async def perform_report_governance_action(
        self,
        *,
        report_id: str,
        action: AdminReportGovernanceAction,
        actor: AdministrationActor,
    ) -> GovernanceActionResult | None:
        raise NotImplementedError

    @abstractmethod
    async def get_report_evidence(
        self,
        *,
        report_id: str,
        evidence_id: str,
        administrator_user_id: str,
    ) -> AdminEvidenceFile | None:
        """Load one submitted evidence file and audit the evidence view."""

        raise NotImplementedError
