"""Authentication, authorization, and contract tests for presence APIs."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_auth_service, get_presence_service
from app.domains.auth.application.services import AuthService
from app.domains.auth.infrastructure.memory_repository import (
    InMemoryAuthRepository,
)
from app.domains.auth.infrastructure.memory_revocation_store import (
    InMemoryAccessTokenRevocationStore,
)
from app.domains.auth.infrastructure.memory_session_store import (
    InMemoryRefreshSessionStore,
)
from app.domains.auth.infrastructure.memory_ticket_store import (
    InMemoryWebSocketTicketStore,
)
from app.domains.presence.domain.exceptions import (
    PresencePermissionDeniedError,
)
from app.domains.presence.domain.models import OnlineGroupMember
from app.domains.study_groups.domain.models import StudyGroupMemberRole
from app.main import app


GROUP_ID = "11111111-1111-1111-1111-111111111111"


class StubPresenceService:
    """Controllable application service used by endpoint tests."""

    def __init__(self) -> None:
        self.preference = True
        self.allow_group_list = True
        self.heartbeats: list[str] = []
        self.offline: list[str] = []

    async def heartbeat(self, user_id: str) -> bool:
        self.heartbeats.append(user_id)
        return self.preference

    async def mark_offline(self, user_id: str) -> None:
        self.offline.append(user_id)

    async def get_preference(self, user_id: str) -> bool:
        del user_id
        return self.preference

    async def update_preference(
        self,
        *,
        user_id: str,
        enabled: bool,
    ) -> bool:
        del user_id
        self.preference = enabled
        return enabled

    async def list_online_group_members(
        self,
        *,
        group_id: str,
        requester_user_id: str,
    ) -> list[OnlineGroupMember]:
        del group_id, requester_user_id
        if not self.allow_group_list:
            raise PresencePermissionDeniedError(
                "You must be a group member to view online members."
            )
        return [
            OnlineGroupMember(
                user_id="22222222-2222-2222-2222-222222222222",
                full_name="Online Student",
                role=StudyGroupMemberRole.ADMIN,
            )
        ]


@pytest.fixture
def presence_client() -> Iterator[tuple[TestClient, StubPresenceService]]:
    auth_service = AuthService(
        repository=InMemoryAuthRepository(),
        ticket_store=InMemoryWebSocketTicketStore(),
        revocation_store=InMemoryAccessTokenRevocationStore(),
        session_store=InMemoryRefreshSessionStore(),
    )
    presence_service = StubPresenceService()
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[get_presence_service] = lambda: presence_service

    client = TestClient(app)
    try:
        yield client, presence_service
    finally:
        client.close()

    app.dependency_overrides.clear()


def register_and_login(client: TestClient) -> tuple[str, str]:
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Presence Student",
            "email": "presence@example.com",
            "password": "SecurePassword123!",
        },
    )
    assert registration.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "presence@example.com",
            "password": "SecurePassword123!",
        },
    )
    assert login.status_code == 200
    return login.json()["access_token"], registration.json()["id"]


def authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_presence_endpoints_require_authentication(
    presence_client: tuple[TestClient, StubPresenceService],
) -> None:
    client, _ = presence_client

    response = client.post("/api/v1/presence/heartbeat")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_heartbeat_and_privacy_preference_contract(
    presence_client: tuple[TestClient, StubPresenceService],
) -> None:
    client, service = presence_client
    token, user_id = register_and_login(client)
    headers = authorization(token)

    heartbeat = client.post(
        "/api/v1/presence/heartbeat",
        headers=headers,
    )
    assert heartbeat.status_code == 200
    assert heartbeat.json() == {"visible_online": True}
    assert service.heartbeats == [user_id]

    updated = client.patch(
        "/api/v1/presence/preferences",
        headers=headers,
        json={"show_online_status": False},
    )
    assert updated.status_code == 200
    assert updated.json() == {"show_online_status": False}

    preference = client.get(
        "/api/v1/presence/preferences",
        headers=headers,
    )
    assert preference.json() == {"show_online_status": False}

    removed = client.delete(
        "/api/v1/presence/heartbeat",
        headers=headers,
    )
    assert removed.status_code == 204
    assert service.offline == [user_id]


def test_online_group_members_contract_and_authorization(
    presence_client: tuple[TestClient, StubPresenceService],
) -> None:
    client, service = presence_client
    token, _ = register_and_login(client)
    headers = authorization(token)

    response = client.get(
        f"/api/v1/study-groups/{GROUP_ID}/online-members",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json() == {
        "online_count": 1,
        "items": [
            {
                "user_id": "22222222-2222-2222-2222-222222222222",
                "full_name": "Online Student",
                "role": "admin",
            }
        ],
    }

    service.allow_group_list = False
    forbidden = client.get(
        f"/api/v1/study-groups/{GROUP_ID}/online-members",
        headers=headers,
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == (
        "PRESENCE_PERMISSION_DENIED"
    )
