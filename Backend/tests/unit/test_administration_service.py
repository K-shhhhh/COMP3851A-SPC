"""Unit coverage for administration business rules."""

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.domains.administration.application.services import AdministrationService
from app.domains.administration.domain.exceptions import (
    AdministrationConflictError,
    AdministrationValidationError,
)
from app.domains.administration.domain.models import (
    AdminAttachmentDetails,
    AdminAttachmentSummary,
    AdminReportDetails,
    AdminReportGovernanceAction,
    AdminReportResolutionOutcome,
    AdminReportSummary,
    AdminUserDetails,
    AdminUserSummary,
    AdministrationAttachmentSource,
    AdministrationAttachmentStatus,
    AdministrationUserRole,
    AdministrationUserStatus,
    GovernanceActionResult,
)
from app.domains.reports.domain.models import (
    ReportCategory,
    ReportStatus,
    ReportTargetType,
)


NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)


class StubAdministrationRepository:
    def __init__(self) -> None:
        self.active_admins = 2
        self.users = {
            "admin-1": self._user("admin-1", AdministrationUserRole.ADMIN),
            "admin-2": self._user("admin-2", AdministrationUserRole.ADMIN),
            "student-1": self._user("student-1", AdministrationUserRole.STUDENT),
        }
        self.attachment = AdminAttachmentDetails(
            attachment=AdminAttachmentSummary(
                attachment_id=1,
                title="Failed note",
                file_name="failed.pdf",
                uploader_name="Student",
                source=AdministrationAttachmentSource.MY_NOTES,
                file_size_bytes=100,
                status=AdministrationAttachmentStatus.FAILED,
                uploaded_at=NOW,
                removed=False,
            ),
            uploader_user_id="student-1",
            content_type="application/pdf",
            processing_progress=0,
            processing_started_at=NOW,
            processing_completed_at=NOW,
            processing_duration_seconds=10,
            safe_processing_error="Processing failed.",
        )
        self.last_actor = None
        self.report = self._report(ReportStatus.SUBMITTED, ReportTargetType.MESSAGE)
        self.last_report_call = None

    @staticmethod
    def _user(user_id: str, role: AdministrationUserRole) -> AdminUserDetails:
        return AdminUserDetails(
            user=AdminUserSummary(
                user_id=user_id,
                full_name=user_id,
                email=f"{user_id}@example.com",
                role=role,
                status=AdministrationUserStatus.ACTIVE,
                created_at=NOW,
                last_active_at=NOW,
            ),
            notes_count=0,
            groups_joined_count=0,
            groups_owned_count=0,
        )

    async def get_user(self, user_id):
        return self.users.get(user_id)

    async def count_active_administrators(self):
        return self.active_admins

    async def deactivate_user(self, *, user_id, actor):
        self.last_actor = actor
        return GovernanceActionResult(user_id, "deactivated", NOW)

    async def get_attachment(self, attachment_id):
        return self.attachment if attachment_id == 1 else None

    async def retry_attachment(self, *, attachment_id, actor):
        self.last_actor = actor
        return GovernanceActionResult(str(attachment_id), "queued", NOW)

    async def list_system_logs(self, **_):
        raise AssertionError("invalid ranges must fail before persistence")

    @staticmethod
    def _report(status, target_type):
        return AdminReportDetails(
            report=AdminReportSummary(
                report_id="report-1",
                created_at=NOW,
                category=ReportCategory.HARASSMENT_BULLYING,
                target_type=target_type,
                target_description="Reported content",
                status=status,
            ),
            reporter_user_id="student-1",
            reporter_name="Student",
            description="A clear report description",
            target_snapshot={"message": "preserved reported message"},
            limited_context_snapshot=(),
            evidence=(),
            activity=(),
            resolved_at=None,
            resolution_outcome=None,
            internal_resolution_reason=None,
            public_summary=None,
        )

    async def get_report(self, report_id):
        return self.report if report_id == "report-1" else None

    async def start_report_review(self, **values):
        self.last_report_call = values
        return replace(
            self.report,
            report=replace(self.report.report, status=ReportStatus.UNDER_REVIEW),
        )

    async def add_report_note(self, **values):
        self.last_report_call = values
        return self.report

    async def resolve_report(self, **values):
        self.last_report_call = values
        return replace(
            self.report,
            report=replace(self.report.report, status=ReportStatus.RESOLVED),
        )

    async def perform_report_governance_action(self, **values):
        self.last_report_call = values
        return GovernanceActionResult("report-1", "action_completed", NOW)


@pytest.mark.asyncio
async def test_admin_cannot_deactivate_self_or_final_admin() -> None:
    repository = StubAdministrationRepository()
    service = AdministrationService(repository)

    with pytest.raises(AdministrationConflictError, match="own account"):
        await service.deactivate_user(
            current_admin_id="admin-1",
            target_user_id="admin-1",
            reason="A sufficiently clear reason",
        )

    repository.active_admins = 1
    with pytest.raises(AdministrationConflictError, match="final active"):
        await service.deactivate_user(
            current_admin_id="admin-1",
            target_user_id="admin-2",
            reason="A sufficiently clear reason",
        )


@pytest.mark.asyncio
async def test_governance_reason_is_trimmed_and_required() -> None:
    repository = StubAdministrationRepository()
    service = AdministrationService(repository)

    with pytest.raises(AdministrationValidationError, match="10 characters"):
        await service.deactivate_user(
            current_admin_id="admin-1",
            target_user_id="student-1",
            reason=" too short ",
        )

    await service.deactivate_user(
        current_admin_id="admin-1",
        target_user_id="student-1",
        reason="  Confirmed policy violation  ",
    )
    assert repository.last_actor.reason == "Confirmed policy violation"


@pytest.mark.asyncio
async def test_only_failed_active_attachment_can_be_retried() -> None:
    repository = StubAdministrationRepository()
    service = AdministrationService(repository)

    repository.attachment = replace(
        repository.attachment,
        attachment=replace(
            repository.attachment.attachment,
            status=AdministrationAttachmentStatus.READY,
        ),
    )
    with pytest.raises(AdministrationConflictError, match="Only failed"):
        await service.retry_attachment(
            current_admin_id="admin-1",
            attachment_id=1,
            reason="Retry requested after investigation",
        )


@pytest.mark.asyncio
async def test_system_log_range_must_be_ordered() -> None:
    repository = StubAdministrationRepository()
    service = AdministrationService(repository)

    with pytest.raises(AdministrationValidationError, match="occurred_from"):
        await service.list_system_logs(
            severity=None,
            service=None,
            request_id=None,
            occurred_from=datetime(2026, 10, 25, tzinfo=timezone.utc),
            occurred_to=NOW,
            cursor=None,
            limit=25,
        )


@pytest.mark.asyncio
async def test_report_workflow_requires_explicit_review_state() -> None:
    repository = StubAdministrationRepository()
    service = AdministrationService(repository)

    with pytest.raises(AdministrationConflictError, match="under review"):
        await service.add_report_note(
            current_admin_id="admin-1", report_id="report-1", note="Reviewed"
        )

    reviewed = await service.start_report_review(
        current_admin_id="admin-1",
        report_id="report-1",
        reason="Beginning policy investigation",
    )
    assert reviewed.report.status == ReportStatus.UNDER_REVIEW


@pytest.mark.asyncio
async def test_report_resolution_and_action_must_match_target() -> None:
    repository = StubAdministrationRepository()
    repository.report = repository._report(
        ReportStatus.UNDER_REVIEW, ReportTargetType.GROUP
    )
    service = AdministrationService(repository)

    with pytest.raises(AdministrationValidationError, match="outcome"):
        await service.resolve_report(
            current_admin_id="admin-1",
            report_id="report-1",
            outcome=AdminReportResolutionOutcome.FILE_REMOVED,
            reason="Confirmed governance policy violation",
            public_summary="The report was reviewed and actioned.",
        )

    with pytest.raises(AdministrationValidationError, match="action"):
        await service.perform_report_governance_action(
            current_admin_id="admin-1",
            report_id="report-1",
            action=AdminReportGovernanceAction.REMOVE_FILE,
            reason="Confirmed governance policy violation",
        )

    resolved = await service.resolve_report(
        current_admin_id="admin-1",
        report_id="report-1",
        outcome=AdminReportResolutionOutcome.GROUP_REMOVED,
        reason="Confirmed governance policy violation",
        public_summary="The group was removed after review.",
    )
    assert resolved.report.status == ReportStatus.RESOLVED
