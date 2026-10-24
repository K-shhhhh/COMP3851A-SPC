"""RBAC and public-contract tests for administration endpoints."""

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.dependencies import get_administration_service, get_current_user
from app.domains.administration.domain.models import (
    AdminReportDetails,
    AdminReportSummary,
    DashboardSnapshot,
    GovernanceActionResult,
)
from app.domains.reports.domain.models import (
    ReportCategory,
    ReportStatus,
    ReportTargetType,
)
from app.domains.auth.domain.models import User
from app.main import app


NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)


class StubAdministrationService:
    async def get_dashboard(self) -> DashboardSnapshot:
        return DashboardSnapshot(
            active_users=12,
            active_study_groups=4,
            stored_notes=20,
            processing_failures_24h=1,
            open_reports=3,
            under_review_reports=1,
            recently_submitted_reports=2,
            recent_processing_failures=(),
            recent_system_events=(),
            recent_reports=(),
        )

    async def deactivate_user(self, **values) -> GovernanceActionResult:
        assert values["current_admin_id"] == "admin-1"
        return GovernanceActionResult(
            resource_id=values["target_user_id"],
            status="deactivated",
            changed_at=NOW,
        )


def user(role: str) -> User:
    return User(
        id=f"{role}-1",
        full_name=f"{role.title()} User",
        email=f"{role}@example.com",
        role=role,
        is_active=True,
        created_at=NOW,
    )


def test_administration_requires_authentication() -> None:
    client = TestClient(app)
    try:
        response = client.get("/api/v1/administration/me")
        assert response.status_code == 401
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_student_cannot_access_administration() -> None:
    app.dependency_overrides[get_current_user] = lambda: user("student")
    client = TestClient(app)
    try:
        response = client.get("/api/v1/administration/me")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_admin_identity_dashboard_and_governance_contract() -> None:
    app.dependency_overrides[get_current_user] = lambda: user("admin")
    app.dependency_overrides[get_administration_service] = (
        lambda: StubAdministrationService()
    )
    client = TestClient(app)
    try:
        identity = client.get("/api/v1/administration/me")
        assert identity.status_code == 200
        assert identity.json()["role"] == "admin"

        dashboard = client.get("/api/v1/administration/dashboard")
        assert dashboard.status_code == 200
        assert dashboard.json()["active_users"] == 12
        assert dashboard.json()["open_reports"] == 3
        assert dashboard.json()["recent_reports"] == []

        changed = client.post(
            "/api/v1/administration/users/student-1/deactivate",
            json={"reason": "Confirmed account policy violation"},
        )
        assert changed.status_code == 200
        assert changed.json()["status"] == "deactivated"
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_admin_data_returns_explicit_pending_integration_error() -> None:
    app.dependency_overrides[get_current_user] = lambda: user("admin")
    client = TestClient(app)
    try:
        response = client.get("/api/v1/administration/system-status")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "PERSISTENCE_NOT_CONFIGURED"
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_admin_report_management_contract_is_exposed_without_assignment() -> None:
    paths = app.openapi()["paths"]
    expected = {
        "/api/v1/administration/reports",
        "/api/v1/administration/reports/{report_id}",
        "/api/v1/administration/reports/{report_id}/start-review",
        "/api/v1/administration/reports/{report_id}/notes",
        "/api/v1/administration/reports/{report_id}/resolve",
        "/api/v1/administration/reports/{report_id}/dismiss",
        "/api/v1/administration/reports/{report_id}/actions",
        "/api/v1/administration/reports/{report_id}/evidence/{evidence_id}",
    }
    assert expected <= set(paths)
    report_contract = " ".join(
        str(value)
        for path, value in paths.items()
        if path.startswith("/api/v1/administration/reports")
    ).lower()
    assert "priority" not in report_contract
    assert "assigned" not in report_contract
