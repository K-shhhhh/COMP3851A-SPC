"""Security and API contract tests for Study Group endpoints."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_auth_service, get_study_group_service
from app.domains.auth.application.services import AuthService
from app.domains.auth.infrastructure.memory_repository import (
    InMemoryAuthRepository,
)
from app.domains.auth.infrastructure.memory_revocation_store import (
    InMemoryAccessTokenRevocationStore,
)
from app.domains.auth.infrastructure.memory_ticket_store import (
    InMemoryWebSocketTicketStore,
)
from app.domains.study_groups.application.services import StudyGroupService
from app.domains.study_groups.infrastructure.memory_repository import (
    InMemoryStudyGroupRepository,
)
from app.main import app


@pytest.fixture
def study_group_client() -> Iterator[TestClient]:
    """Provide isolated authentication and Study Group adapters."""

    auth_service = AuthService(
        repository=InMemoryAuthRepository(),
        ticket_store=InMemoryWebSocketTicketStore(),
        revocation_store=InMemoryAccessTokenRevocationStore(),
    )
    group_service = StudyGroupService(InMemoryStudyGroupRepository())
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[get_study_group_service] = lambda: group_service

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def register_and_login(client: TestClient, email: str) -> str:
    """Create one student and return a bearer token."""

    payload = {
        "full_name": "Study Group Student",
        "email": email,
        "password": "SecurePassword123!",
    }
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": payload["password"]},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


def headers(token: str) -> dict[str, str]:
    """Build an authorization header."""

    return {"Authorization": f"Bearer {token}"}


def test_study_groups_require_authentication(study_group_client) -> None:
    """Reject anonymous discovery and creation."""

    assert study_group_client.get(
        "/api/v1/study-groups/discover"
    ).status_code == 401
    assert study_group_client.post(
        "/api/v1/study-groups",
        json={
            "name": "Anonymous",
            "description": None,
            "visibility": "public",
            "max_members": 5,
        },
    ).status_code == 401


def test_public_discovery_join_and_cross_user_permissions(
    study_group_client,
) -> None:
    """Verify the main two-user public group workflow."""

    owner_token = register_and_login(
        study_group_client, "group-owner@example.com"
    )
    member_token = register_and_login(
        study_group_client, "group-member@example.com"
    )
    created = study_group_client.post(
        "/api/v1/study-groups",
        headers=headers(owner_token),
        json={
            "name": "Algorithms",
            "description": "Revision",
            "visibility": "public",
            "max_members": 4,
        },
    )
    assert created.status_code == 201
    group_id = created.json()["id"]
    assert created.json()["is_owner"] is True
    assert created.json()["member_count"] == 1

    discovered = study_group_client.get(
        "/api/v1/study-groups/discover",
        headers=headers(member_token),
    )
    assert discovered.status_code == 200
    assert discovered.json()["items"][0]["is_member"] is False

    joined = study_group_client.post(
        f"/api/v1/study-groups/{group_id}/join",
        headers=headers(member_token),
    )
    assert joined.status_code == 201
    assert joined.json()["member_count"] == 2

    forbidden = study_group_client.put(
        f"/api/v1/study-groups/{group_id}",
        headers=headers(member_token),
        json={
            "name": "Hijacked",
            "description": None,
            "visibility": "public",
            "max_members": 4,
        },
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == (
        "STUDY_GROUP_PERMISSION_DENIED"
    )


def test_private_group_is_hidden_from_unrelated_user(
    study_group_client,
) -> None:
    """Do not disclose private groups through discovery or direct access."""

    owner_token = register_and_login(
        study_group_client, "private-owner@example.com"
    )
    outsider_token = register_and_login(
        study_group_client, "private-outsider@example.com"
    )
    created = study_group_client.post(
        "/api/v1/study-groups",
        headers=headers(owner_token),
        json={
            "name": "Private exam prep",
            "description": None,
            "visibility": "private",
            "max_members": 5,
        },
    )
    group_id = created.json()["id"]

    discovery = study_group_client.get(
        "/api/v1/study-groups/discover",
        headers=headers(outsider_token),
    )
    assert discovery.json()["total"] == 0
    hidden = study_group_client.get(
        f"/api/v1/study-groups/{group_id}",
        headers=headers(outsider_token),
    )
    assert hidden.status_code == 404
    join = study_group_client.post(
        f"/api/v1/study-groups/{group_id}/join",
        headers=headers(outsider_token),
    )
    assert join.status_code == 403
    assert join.json()["error"]["code"] == (
        "PRIVATE_GROUP_INVITATION_REQUIRED"
    )
