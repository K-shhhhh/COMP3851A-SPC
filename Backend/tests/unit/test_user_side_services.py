"""Unit coverage for profile, settings, password, and report use cases."""

from datetime import datetime, timezone

import pytest

from app.core.security import hash_password, verify_password
from app.domains.auth.application.services import PasswordChangeService
from app.domains.auth.domain.exceptions import (
    CurrentPasswordIncorrectError,
    PasswordReuseError,
)
from app.domains.auth.domain.password_repository import PasswordChangeRepository
from app.domains.notifications.application.services import NotificationPreferenceService
from app.domains.notifications.domain.models import NotificationPreferences
from app.domains.notifications.domain.repository import NotificationPreferenceRepository
from app.domains.reports.application.services import ReportService
from app.domains.reports.domain.exceptions import InvalidEvidenceError, ReportNotFoundError
from app.domains.reports.domain.models import (
    EvidenceUpload,
    Report,
    ReportCategory,
    ReportPage,
    ReportStatus,
    ReportTargetType,
)
from app.domains.reports.domain.repository import ReportRepository
from app.domains.users.application.services import UserProfileService
from app.domains.users.domain.exceptions import UserProfileNotFoundError
from app.domains.users.domain.models import UserProfile, UserProfileChanges
from app.domains.users.domain.repository import UserProfileRepository


pytestmark = pytest.mark.asyncio


class FakeProfileRepository(UserProfileRepository):
    def __init__(self) -> None:
        self.profile = UserProfile(
            user_id="student-1",
            full_name="Student One",
            email="student@example.com",
            programme=None,
            year_of_study=None,
            bio=None,
            account_type="student",
            status="active",
        )
        self.last_changes: UserProfileChanges | None = None

    async def get_profile(self, user_id: str) -> UserProfile | None:
        return self.profile if user_id == self.profile.user_id else None

    async def update_profile(
        self, *, user_id: str, changes: UserProfileChanges
    ) -> UserProfile | None:
        if user_id != self.profile.user_id:
            return None
        self.last_changes = changes
        self.profile = UserProfile(
            user_id=self.profile.user_id,
            full_name=changes.full_name or self.profile.full_name,
            email=self.profile.email,
            programme=changes.programme,
            year_of_study=changes.year_of_study,
            bio=changes.bio,
            account_type=self.profile.account_type,
            status=self.profile.status,
        )
        return self.profile


class FakeNotificationRepository(NotificationPreferenceRepository):
    def __init__(self) -> None:
        self.value = NotificationPreferences(True, True)

    async def get_preferences(self, user_id: str) -> NotificationPreferences:
        del user_id
        return self.value

    async def update_preferences(
        self,
        *,
        user_id: str,
        new_group_messages: bool | None,
        group_mentions: bool | None,
    ) -> NotificationPreferences:
        del user_id
        self.value = NotificationPreferences(
            self.value.new_group_messages
            if new_group_messages is None
            else new_group_messages,
            self.value.group_mentions if group_mentions is None else group_mentions,
        )
        return self.value


class FakePasswordRepository(PasswordChangeRepository):
    def __init__(self) -> None:
        self.password_hash = hash_password("CurrentPassword123!")

    async def get_password_hash(self, user_id: str) -> str | None:
        return self.password_hash if user_id == "student-1" else None

    async def update_password_hash(self, *, user_id: str, password_hash: str) -> bool:
        if user_id != "student-1":
            return False
        self.password_hash = password_hash
        return True


class FakeReportRepository(ReportRepository):
    def __init__(self) -> None:
        self.report: Report | None = None

    async def create_report(self, **values) -> Report:
        now = datetime.now(timezone.utc)
        self.report = Report(
            report_id="report-1",
            reporter_user_id=values["reporter_user_id"],
            target_type=values["target_type"],
            target_id=values["target_id"],
            category=values["category"],
            description=values["description"],
            status=ReportStatus.SUBMITTED,
            target_snapshot={"message": "immutable snapshot"},
            limited_context_snapshot=[],
            evidence=[],
            created_at=now,
            updated_at=now,
        )
        return self.report

    async def list_reports(
        self, *, reporter_user_id: str, status, cursor, limit
    ) -> ReportPage:
        del status, cursor, limit
        items = (
            [self.report]
            if self.report and self.report.reporter_user_id == reporter_user_id
            else []
        )
        return ReportPage(items=items, next_cursor=None)

    async def get_report(
        self, *, reporter_user_id: str, report_id: str
    ) -> Report | None:
        if (
            self.report
            and self.report.report_id == report_id
            and self.report.reporter_user_id == reporter_user_id
        ):
            return self.report
        return None


async def test_profile_service_scopes_access_to_requested_user() -> None:
    repository = FakeProfileRepository()
    service = UserProfileService(repository)
    updated = await service.update_profile(
        user_id="student-1",
        changes=UserProfileChanges(
            full_name="Updated Student",
            changed_fields=frozenset({"full_name"}),
        ),
    )
    assert updated.full_name == "Updated Student"
    assert repository.last_changes is not None
    assert repository.last_changes.changed_fields == {"full_name"}
    with pytest.raises(UserProfileNotFoundError):
        await service.get_profile("another-user")


async def test_notification_preferences_update_independently() -> None:
    service = NotificationPreferenceService(FakeNotificationRepository())
    result = await service.update_preferences(
        user_id="student-1",
        new_group_messages=False,
        group_mentions=None,
    )
    assert result == NotificationPreferences(False, True)


async def test_password_change_verifies_current_and_rejects_reuse() -> None:
    repository = FakePasswordRepository()
    service = PasswordChangeService(repository)
    with pytest.raises(CurrentPasswordIncorrectError):
        await service.change_password(
            user_id="student-1",
            current_password="wrong",
            new_password="DifferentPassword123!",
        )
    with pytest.raises(PasswordReuseError):
        await service.change_password(
            user_id="student-1",
            current_password="CurrentPassword123!",
            new_password="CurrentPassword123!",
        )
    await service.change_password(
        user_id="student-1",
        current_password="CurrentPassword123!",
        new_password="DifferentPassword123!",
    )
    assert verify_password("DifferentPassword123!", repository.password_hash)


async def test_report_validation_and_submitter_scope() -> None:
    repository = FakeReportRepository()
    service = ReportService(repository)
    with pytest.raises(InvalidEvidenceError):
        await service.create_report(
            reporter_user_id="student-1",
            target_type=ReportTargetType.MESSAGE,
            target_id="message-1",
            category=ReportCategory.HARASSMENT_BULLYING,
            description="This message contains targeted harassment.",
            include_limited_context=False,
            evidence=[EvidenceUpload("proof.gif", "image/gif", b"gif")],
        )
    created = await service.create_report(
        reporter_user_id="student-1",
        target_type=ReportTargetType.MESSAGE,
        target_id="message-1",
        category=ReportCategory.HARASSMENT_BULLYING,
        description="This message contains targeted harassment.",
        include_limited_context=True,
        evidence=[
            EvidenceUpload("proof.png", "image/png", b"\x89PNG\r\n\x1a\nproof")
        ],
    )
    assert created.status is ReportStatus.SUBMITTED
    with pytest.raises(ReportNotFoundError):
        await service.get_report(reporter_user_id="student-2", report_id="report-1")
