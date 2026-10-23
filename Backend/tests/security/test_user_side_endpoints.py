"""Authentication and public-contract tests for student-side endpoints."""

from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_auth_service,
    get_notification_preference_service,
    get_password_change_service,
    get_report_service,
    get_user_profile_service,
)
from app.domains.auth.application.services import AuthService
from app.domains.auth.infrastructure.memory_repository import InMemoryAuthRepository
from app.domains.auth.infrastructure.memory_revocation_store import (
    InMemoryAccessTokenRevocationStore,
)
from app.domains.auth.infrastructure.memory_session_store import InMemoryRefreshSessionStore
from app.domains.auth.infrastructure.memory_ticket_store import InMemoryWebSocketTicketStore
from app.domains.notifications.domain.models import NotificationPreferences
from app.domains.reports.domain.models import (
    Report,
    ReportCategory,
    ReportPage,
    ReportStatus,
    ReportTargetType,
)
from app.domains.users.domain.models import UserProfile
from app.main import app


class StubProfileService:
    async def get_profile(self, user_id: str) -> UserProfile:
        return self._profile(user_id, "Student User")

    async def update_profile(self, *, user_id: str, changes) -> UserProfile:
        return self._profile(user_id, changes.full_name or "Student User")

    @staticmethod
    def _profile(user_id: str, name: str) -> UserProfile:
        return UserProfile(
            user_id=user_id,
            full_name=name,
            email="student@example.com",
            programme="Computer Science",
            year_of_study=3,
            bio="Student bio",
            account_type="student",
            status="active",
        )


class StubNotificationService:
    async def get_preferences(self, user_id: str) -> NotificationPreferences:
        del user_id
        return NotificationPreferences(True, True)

    async def update_preferences(self, **values) -> NotificationPreferences:
        return NotificationPreferences(
            values["new_group_messages"] if values["new_group_messages"] is not None else True,
            values["group_mentions"] if values["group_mentions"] is not None else True,
        )


class StubPasswordService:
    def __init__(self) -> None:
        self.changed_for: str | None = None

    async def change_password(self, *, user_id: str, **_) -> None:
        self.changed_for = user_id


class StubReportService:
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
            target_snapshot={"message": "snapshot"},
            limited_context_snapshot=[],
            evidence=[],
            created_at=now,
            updated_at=now,
        )
        return self.report

    async def list_reports(self, **_) -> ReportPage:
        return ReportPage(items=[self.report] if self.report else [], next_cursor=None)

    async def get_report(self, **_) -> Report:
        assert self.report is not None
        return self.report


@pytest.fixture
def client() -> Iterator[TestClient]:
    auth_service = AuthService(
        repository=InMemoryAuthRepository(),
        ticket_store=InMemoryWebSocketTicketStore(),
        revocation_store=InMemoryAccessTokenRevocationStore(),
        session_store=InMemoryRefreshSessionStore(),
    )
    profile_service = StubProfileService()
    notification_service = StubNotificationService()
    password_service = StubPasswordService()
    report_service = StubReportService()
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[get_user_profile_service] = lambda: profile_service
    app.dependency_overrides[get_notification_preference_service] = (
        lambda: notification_service
    )
    app.dependency_overrides[get_password_change_service] = lambda: password_service
    app.dependency_overrides[get_report_service] = lambda: report_service
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        test_client.close()
        app.dependency_overrides.clear()


def login(client: TestClient) -> dict[str, str]:
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Student User",
            "email": "student@example.com",
            "password": "SecurePassword123!",
        },
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "student@example.com", "password": "SecurePassword123!"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_user_side_endpoints_require_authentication(client: TestClient) -> None:
    for method, path in (
        ("get", "/api/v1/users/me/profile"),
        ("get", "/api/v1/notifications/preferences"),
        ("get", "/api/v1/reports"),
    ):
        response = getattr(client, method)(path)
        assert response.status_code == 401


def test_profile_settings_password_and_reports_contract(client: TestClient) -> None:
    headers = login(client)
    profile = client.patch(
        "/api/v1/users/me/profile",
        headers=headers,
        json={"full_name": "Updated Student"},
    )
    assert profile.status_code == 200
    assert profile.json()["full_name"] == "Updated Student"
    assert "role" not in profile.json()

    preferences = client.patch(
        "/api/v1/notifications/preferences",
        headers=headers,
        json={"new_group_messages": False},
    )
    assert preferences.json() == {"new_group_messages": False, "group_mentions": True}

    password = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": "SecurePassword123!", "new_password": "NewPassword123!"},
    )
    assert password.status_code == 204

    submitted = client.post(
        "/api/v1/reports",
        headers=headers,
        data={
            "target_type": ReportTargetType.MESSAGE.value,
            "target_id": "message-1",
            "category": ReportCategory.HARASSMENT_BULLYING.value,
            "description": "This selected message contains targeted harassment.",
            "include_limited_context": "true",
        },
        files={
            "evidence": (
                "proof.png",
                b"\x89PNG\r\n\x1a\nproof",
                "image/png",
            )
        },
    )
    assert submitted.status_code == 201
    assert submitted.json()["status"] == "submitted"

    reports = client.get("/api/v1/reports", headers=headers)
    assert reports.status_code == 200
    assert len(reports.json()["items"]) == 1
