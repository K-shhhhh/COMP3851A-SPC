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
    AdminUserDetails,
    AdminUserSummary,
    AdministrationAttachmentSource,
    AdministrationAttachmentStatus,
    AdministrationUserRole,
    AdministrationUserStatus,
    GovernanceActionResult,
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
