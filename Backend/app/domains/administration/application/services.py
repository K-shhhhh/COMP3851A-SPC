"""Authorization-independent administration business rules.

FastAPI verifies that the caller is an administrator. This service validates
resource state and delegates atomic persistence plus audit logging through the
repository contract.
"""

from datetime import datetime

from app.domains.administration.domain.exceptions import (
    AdministrationConflictError,
    AdministrationResourceNotFoundError,
    AdministrationValidationError,
)
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
from app.domains.administration.domain.repository import AdministrationRepository
from app.domains.reports.domain.models import ReportStatus, ReportTargetType


class AdministrationService:
    def __init__(self, repository: AdministrationRepository) -> None:
        self.repository = repository

    async def get_system_status(self) -> SystemStatus:
        return await self.repository.get_system_status()

    async def get_dashboard(self) -> DashboardSnapshot:
        return await self.repository.get_dashboard()

    async def list_users(
        self,
        *,
        search: str | None,
        status: AdministrationUserStatus | None,
        role: AdministrationUserRole | None,
        cursor: str | None,
        limit: int,
    ) -> AdminUserPage:
        return await self.repository.list_users(
            search=self._clean_optional(search),
            status=status,
            role=role,
            cursor=cursor,
            limit=limit,
        )

    async def get_user(self, user_id: str) -> AdminUserDetails:
        user = await self.repository.get_user(user_id)
        if user is None:
            raise AdministrationResourceNotFoundError("The user was not found.")
        return user

    async def deactivate_user(
        self,
        *,
        current_admin_id: str,
        target_user_id: str,
        reason: str,
    ) -> GovernanceActionResult:
        if current_admin_id == target_user_id:
            raise AdministrationConflictError(
                "Administrators cannot deactivate their own account."
            )
        target = await self.get_user(target_user_id)
        if target.user.status == AdministrationUserStatus.DEACTIVATED:
            raise AdministrationConflictError("The account is already deactivated.")
        if (
            target.user.role == AdministrationUserRole.ADMIN
            and await self.repository.count_active_administrators() <= 1
        ):
            raise AdministrationConflictError(
                "The final active administrator cannot be deactivated."
            )
        result = await self.repository.deactivate_user(
            user_id=target_user_id,
            actor=self._actor(current_admin_id, reason),
        )
        return self._require_result(result, "The user was not found.")

    async def reactivate_user(
        self,
        *,
        current_admin_id: str,
        target_user_id: str,
        reason: str,
    ) -> GovernanceActionResult:
        target = await self.get_user(target_user_id)
        if target.user.status == AdministrationUserStatus.ACTIVE:
            raise AdministrationConflictError("The account is already active.")
        result = await self.repository.reactivate_user(
            user_id=target_user_id,
            actor=self._actor(current_admin_id, reason),
        )
        return self._require_result(result, "The user was not found.")

    async def list_groups(
        self,
        *,
        search: str | None,
        visibility: AdministrationGroupVisibility | None,
        status: AdministrationGroupStatus | None,
        cursor: str | None,
        limit: int,
    ) -> AdminGroupPage:
        return await self.repository.list_groups(
            search=self._clean_optional(search),
            visibility=visibility,
            status=status,
            cursor=cursor,
            limit=limit,
        )

    async def get_group(self, group_id: str) -> AdminGroupDetails:
        group = await self.repository.get_group(group_id)
        if group is None:
            raise AdministrationResourceNotFoundError("The study group was not found.")
        return group

    async def remove_group(
        self,
        *,
        current_admin_id: str,
        group_id: str,
        reason: str,
    ) -> GovernanceActionResult:
        group = await self.get_group(group_id)
        if group.group.status == AdministrationGroupStatus.REMOVED:
            raise AdministrationConflictError("The study group is already removed.")
        result = await self.repository.remove_group(
            group_id=group_id,
            actor=self._actor(current_admin_id, reason),
        )
        return self._require_result(result, "The study group was not found.")

    async def restore_group(
        self,
        *,
        current_admin_id: str,
        group_id: str,
        reason: str,
    ) -> GovernanceActionResult:
        group = await self.get_group(group_id)
        if group.group.status == AdministrationGroupStatus.ACTIVE:
            raise AdministrationConflictError("The study group is already active.")
        result = await self.repository.restore_group(
            group_id=group_id,
            actor=self._actor(current_admin_id, reason),
        )
        return self._require_result(result, "The study group was not found.")

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
        return await self.repository.list_attachments(
            search=self._clean_optional(search),
            status=status,
            source=source,
            include_removed=include_removed,
            cursor=cursor,
            limit=limit,
        )

    async def get_attachment(self, attachment_id: int) -> AdminAttachmentDetails:
        attachment = await self.repository.get_attachment(attachment_id)
        if attachment is None:
            raise AdministrationResourceNotFoundError("The attachment was not found.")
        return attachment

    async def remove_attachment(
        self,
        *,
        current_admin_id: str,
        attachment_id: int,
        reason: str,
    ) -> GovernanceActionResult:
        attachment = await self.get_attachment(attachment_id)
        if attachment.attachment.removed:
            raise AdministrationConflictError("The attachment is already removed.")
        result = await self.repository.remove_attachment(
            attachment_id=attachment_id,
            actor=self._actor(current_admin_id, reason),
        )
        return self._require_result(result, "The attachment was not found.")

    async def retry_attachment(
        self,
        *,
        current_admin_id: str,
        attachment_id: int,
        reason: str,
    ) -> GovernanceActionResult:
        attachment = await self.get_attachment(attachment_id)
        if attachment.attachment.removed:
            raise AdministrationConflictError("A removed attachment cannot be retried.")
        if attachment.attachment.status != AdministrationAttachmentStatus.FAILED:
            raise AdministrationConflictError(
                "Only failed attachments can be retried."
            )
        result = await self.repository.retry_attachment(
            attachment_id=attachment_id,
            actor=self._actor(current_admin_id, reason),
        )
        return self._require_result(result, "The attachment was not found.")

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
        if occurred_from and occurred_to and occurred_from > occurred_to:
            raise AdministrationValidationError(
                "occurred_from must not be after occurred_to."
            )
        return await self.repository.list_system_logs(
            severity=severity,
            service=self._clean_optional(service),
            request_id=self._clean_optional(request_id),
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            cursor=cursor,
            limit=limit,
        )

    async def get_system_log(self, event_id: str) -> SystemLogEntry:
        event = await self.repository.get_system_log(event_id)
        if event is None:
            raise AdministrationResourceNotFoundError("The system log was not found.")
        return event

    async def list_reports(
        self,
        *,
        search: str | None,
        status: ReportStatus | None,
        target_type: ReportTargetType | None,
        cursor: str | None,
        limit: int,
    ) -> AdminReportPage:
        return await self.repository.list_reports(
            search=self._clean_optional(search),
            status=status,
            target_type=target_type,
            cursor=cursor,
            limit=limit,
        )

    async def get_report(self, report_id: str) -> AdminReportDetails:
        report = await self.repository.get_report(report_id)
        if report is None:
            raise AdministrationResourceNotFoundError("The report was not found.")
        return report

    async def start_report_review(
        self, *, current_admin_id: str, report_id: str, reason: str
    ) -> AdminReportDetails:
        report = await self.get_report(report_id)
        if report.report.status != ReportStatus.SUBMITTED:
            raise AdministrationConflictError(
                "Only a submitted report can enter review."
            )
        result = await self.repository.start_report_review(
            report_id=report_id,
            actor=self._actor(current_admin_id, reason),
        )
        return self._require_report(result)

    async def add_report_note(
        self, *, current_admin_id: str, report_id: str, note: str
    ) -> AdminReportDetails:
        report = await self._require_report_under_review(report_id)
        clean_note = note.strip()
        if len(clean_note) < 2:
            raise AdministrationValidationError(
                "An internal note must contain at least 2 characters."
            )
        result = await self.repository.add_report_note(
            report_id=report.report.report_id,
            administrator_user_id=current_admin_id,
            note=clean_note,
        )
        return self._require_report(result)

    async def resolve_report(
        self,
        *,
        current_admin_id: str,
        report_id: str,
        outcome: AdminReportResolutionOutcome,
        reason: str,
        public_summary: str,
    ) -> AdminReportDetails:
        report = await self._require_report_under_review(report_id)
        self._validate_resolution_outcome(report.report.target_type, outcome)
        result = await self.repository.resolve_report(
            report_id=report_id,
            administrator_user_id=current_admin_id,
            outcome=outcome,
            internal_reason=self._reason(reason),
            public_summary=self._public_summary(public_summary),
        )
        return self._require_report(result)

    async def dismiss_report(
        self,
        *,
        current_admin_id: str,
        report_id: str,
        reason: str,
        public_summary: str,
    ) -> AdminReportDetails:
        await self._require_report_under_review(report_id)
        result = await self.repository.dismiss_report(
            report_id=report_id,
            administrator_user_id=current_admin_id,
            internal_reason=self._reason(reason),
            public_summary=self._public_summary(public_summary),
        )
        return self._require_report(result)

    async def perform_report_governance_action(
        self,
        *,
        current_admin_id: str,
        report_id: str,
        action: AdminReportGovernanceAction,
        reason: str,
    ) -> GovernanceActionResult:
        report = await self._require_report_under_review(report_id)
        allowed = {
            ReportTargetType.MESSAGE: {
                AdminReportGovernanceAction.REMOVE_MESSAGE,
                AdminReportGovernanceAction.DEACTIVATE_MESSAGE_AUTHOR,
            },
            ReportTargetType.GROUP: {AdminReportGovernanceAction.REMOVE_GROUP},
            ReportTargetType.FILE: {AdminReportGovernanceAction.REMOVE_FILE},
        }
        if action not in allowed[report.report.target_type]:
            raise AdministrationValidationError(
                "The governance action does not match the report target."
            )
        result = await self.repository.perform_report_governance_action(
            report_id=report_id,
            action=action,
            actor=self._actor(current_admin_id, reason),
        )
        return self._require_result(result, "The report was not found.")

    async def get_report_evidence(
        self,
        *,
        current_admin_id: str,
        report_id: str,
        evidence_id: str,
    ) -> AdminEvidenceFile:
        report = await self.get_report(report_id)
        if not any(item.evidence_id == evidence_id for item in report.evidence):
            raise AdministrationResourceNotFoundError(
                "The report evidence was not found."
            )
        evidence = await self.repository.get_report_evidence(
            report_id=report_id,
            evidence_id=evidence_id,
            administrator_user_id=current_admin_id,
        )
        if evidence is None:
            raise AdministrationResourceNotFoundError(
                "The report evidence was not found."
            )
        return evidence

    async def _require_report_under_review(self, report_id: str) -> AdminReportDetails:
        report = await self.get_report(report_id)
        if report.report.status != ReportStatus.UNDER_REVIEW:
            raise AdministrationConflictError(
                "This action is available only while the report is under review."
            )
        return report

    @staticmethod
    def _validate_resolution_outcome(
        target_type: ReportTargetType,
        outcome: AdminReportResolutionOutcome,
    ) -> None:
        common = {
            AdminReportResolutionOutcome.NO_VIOLATION,
            AdminReportResolutionOutcome.DUPLICATE,
            AdminReportResolutionOutcome.INSUFFICIENT_EVIDENCE,
        }
        target_outcomes = {
            ReportTargetType.MESSAGE: {
                AdminReportResolutionOutcome.CONTENT_REMOVED,
                AdminReportResolutionOutcome.USER_DEACTIVATED,
            },
            ReportTargetType.GROUP: {AdminReportResolutionOutcome.GROUP_REMOVED},
            ReportTargetType.FILE: {AdminReportResolutionOutcome.FILE_REMOVED},
        }
        if outcome not in common | target_outcomes[target_type]:
            raise AdministrationValidationError(
                "The resolution outcome does not match the report target."
            )

    @staticmethod
    def _reason(value: str) -> str:
        return AdministrationService._actor("validation-only", value).reason

    @staticmethod
    def _public_summary(value: str) -> str:
        clean = value.strip()
        if len(clean) < 10:
            raise AdministrationValidationError(
                "A public resolution summary must contain at least 10 characters."
            )
        return clean

    @staticmethod
    def _require_report(result: AdminReportDetails | None) -> AdminReportDetails:
        if result is None:
            raise AdministrationResourceNotFoundError("The report was not found.")
        return result

    @staticmethod
    def _actor(user_id: str, reason: str) -> AdministrationActor:
        clean_reason = reason.strip()
        if len(clean_reason) < 10:
            raise AdministrationValidationError(
                "An administrative reason must contain at least 10 characters."
            )
        return AdministrationActor(user_id=user_id, reason=clean_reason)

    @staticmethod
    def _clean_optional(value: str | None) -> str | None:
        if value is None:
            return None
        clean = value.strip()
        return clean or None

    @staticmethod
    def _require_result(
        result: GovernanceActionResult | None,
        not_found_message: str,
    ) -> GovernanceActionResult:
        if result is None:
            raise AdministrationResourceNotFoundError(not_found_message)
        return result
