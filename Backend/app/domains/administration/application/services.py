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
    AdminGroupDetails,
    AdminGroupPage,
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
