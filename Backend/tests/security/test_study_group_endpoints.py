"""Security and API contract tests for Study Group endpoints."""

from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

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
from app.domains.chats.domain.models import ChatSource
from app.domains.chats.domain.retrieval import GroundingChunk
from app.domains.chats.infrastructure.memory_answering import (
    LocalGroundedAnswerGenerator,
)
from app.domains.study_groups.application.services import StudyGroupService
from app.domains.study_groups.infrastructure.memory_repository import (
    InMemoryStudyGroupRepository,
)
from app.domains.study_groups.infrastructure.memory_retrieval import (
    InMemoryStudyGroupReadyChunkRepository,
)
from app.main import app


@dataclass
class MemberManagementContext:
    """HTTP client and test repository used by membership endpoint tests."""

    client: TestClient
    repository: InMemoryStudyGroupRepository


@dataclass
class GroupAiContext:
    """HTTP client and seedable channel chunks for companion API tests."""

    client: TestClient
    chunk_repository: InMemoryStudyGroupReadyChunkRepository


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


@pytest.fixture
def member_management_context() -> Iterator[MemberManagementContext]:
    """Provide a repository that can seed public user profiles by email."""

    auth_service = AuthService(
        repository=InMemoryAuthRepository(),
        ticket_store=InMemoryWebSocketTicketStore(),
        revocation_store=InMemoryAccessTokenRevocationStore(),
    )
    repository = InMemoryStudyGroupRepository()
    group_service = StudyGroupService(repository)
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[get_study_group_service] = lambda: group_service

    with TestClient(app) as client:
        yield MemberManagementContext(client=client, repository=repository)

    app.dependency_overrides.clear()


@pytest.fixture
def group_ai_context() -> Iterator[GroupAiContext]:
    """Provide isolated Study Group AI adapters without external model I/O."""

    auth_service = AuthService(
        repository=InMemoryAuthRepository(),
        ticket_store=InMemoryWebSocketTicketStore(),
        revocation_store=InMemoryAccessTokenRevocationStore(),
    )
    chunk_repository = InMemoryStudyGroupReadyChunkRepository()
    group_service = StudyGroupService(
        InMemoryStudyGroupRepository(),
        chunk_repository=chunk_repository,
        answer_generator=LocalGroundedAnswerGenerator(),
    )
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[get_study_group_service] = lambda: group_service

    with TestClient(app) as client:
        yield GroupAiContext(
            client=client,
            chunk_repository=chunk_repository,
        )

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


def register_login_and_get_id(
    client: TestClient,
    email: str,
) -> tuple[str, str]:
    """Create one student and return its bearer token and UUID."""

    payload = {
        "full_name": "Study Group Student",
        "email": email,
        "password": "SecurePassword123!",
    }
    registration = client.post("/api/v1/auth/register", json=payload)
    assert registration.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": payload["password"]},
    )
    assert login.status_code == 200
    return login.json()["access_token"], registration.json()["id"]


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

    left = study_group_client.delete(
        f"/api/v1/study-groups/{group_id}/members/me",
        headers=headers(member_token),
    )
    assert left.status_code == 204


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


def test_group_channel_api_lifecycle_and_permissions(
    study_group_client,
) -> None:
    """Verify authenticated member reads and owner-only channel management."""

    owner_token = register_and_login(
        study_group_client, "channel-owner@example.com"
    )
    member_token = register_and_login(
        study_group_client, "channel-member@example.com"
    )
    created_group = study_group_client.post(
        "/api/v1/study-groups",
        headers=headers(owner_token),
        json={
            "name": "Channel API group",
            "description": None,
            "visibility": "public",
            "max_members": 5,
        },
    )
    group_id = created_group.json()["id"]
    assert study_group_client.post(
        f"/api/v1/study-groups/{group_id}/join",
        headers=headers(member_token),
    ).status_code == 201

    created = study_group_client.post(
        f"/api/v1/study-groups/{group_id}/channels",
        headers=headers(owner_token),
        json={
            "name": "Exam preparation",
            "description": "Week 8 revision",
        },
    )
    assert created.status_code == 201
    channel_id = created.json()["id"]

    listed = study_group_client.get(
        f"/api/v1/study-groups/{group_id}/channels",
        headers=headers(member_token),
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == channel_id

    forbidden = study_group_client.put(
        f"/api/v1/study-groups/{group_id}/channels/{channel_id}",
        headers=headers(member_token),
        json={"name": "Hijacked", "description": None},
    )
    assert forbidden.status_code == 403

    duplicate = study_group_client.post(
        f"/api/v1/study-groups/{group_id}/channels",
        headers=headers(owner_token),
        json={"name": "EXAM PREPARATION", "description": None},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == (
        "STUDY_GROUP_CHANNEL_NAME_CONFLICT"
    )

    updated = study_group_client.put(
        f"/api/v1/study-groups/{group_id}/channels/{channel_id}",
        headers=headers(owner_token),
        json={"name": "Final exam", "description": None},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Final exam"

    deleted = study_group_client.delete(
        f"/api/v1/study-groups/{group_id}/channels/{channel_id}",
        headers=headers(owner_token),
    )
    assert deleted.status_code == 204
    assert study_group_client.get(
        f"/api/v1/study-groups/{group_id}/channels/{channel_id}",
        headers=headers(member_token),
    ).status_code == 404


def test_normal_group_message_api_lifecycle_and_isolation(
    study_group_client,
) -> None:
    """Verify member messaging, author permissions, and channel isolation."""

    owner_token, owner_id = register_login_and_get_id(
        study_group_client, "message-owner@example.com"
    )
    author_token, author_id = register_login_and_get_id(
        study_group_client, "message-author@example.com"
    )
    outsider_token, outsider_id = register_login_and_get_id(
        study_group_client, "message-outsider@example.com"
    )
    group = study_group_client.post(
        "/api/v1/study-groups",
        headers=headers(owner_token),
        json={
            "name": "Message API group",
            "description": None,
            "visibility": "public",
            "max_members": 5,
        },
    ).json()
    group_id = group["id"]
    assert study_group_client.post(
        f"/api/v1/study-groups/{group_id}/join",
        headers=headers(author_token),
    ).status_code == 201

    first_channel = study_group_client.post(
        f"/api/v1/study-groups/{group_id}/channels",
        headers=headers(owner_token),
        json={"name": "General", "description": None},
    ).json()
    second_channel = study_group_client.post(
        f"/api/v1/study-groups/{group_id}/channels",
        headers=headers(owner_token),
        json={"name": "Revision", "description": None},
    ).json()

    created = study_group_client.post(
        f"/api/v1/study-groups/{group_id}/channels/"
        f"{first_channel['id']}/messages",
        headers=headers(author_token),
        json={
            "content": "  Hello from the group  ",
            "mentioned_user_ids": [owner_id, owner_id],
        },
    )
    assert created.status_code == 201
    assert created.json()["content"] == "Hello from the group"
    assert created.json()["mentioned_user_ids"] == [owner_id]
    message_id = created.json()["id"]

    invalid_mention = study_group_client.post(
        f"/api/v1/study-groups/{group_id}/channels/"
        f"{first_channel['id']}/messages",
        headers=headers(author_token),
        json={
            "content": "Outsider mention",
            "mentioned_user_ids": [outsider_id],
        },
    )
    assert invalid_mention.status_code == 422
    assert invalid_mention.json()["error"]["code"] == (
        "STUDY_GROUP_MENTIONED_USER_NOT_MEMBER"
    )

    history = study_group_client.get(
        f"/api/v1/study-groups/{group_id}/channels/"
        f"{first_channel['id']}/messages",
        headers=headers(owner_token),
    )
    assert history.status_code == 200
    assert history.json()["total"] == 1

    assert study_group_client.get(
        f"/api/v1/study-groups/{group_id}/channels/"
        f"{first_channel['id']}/messages",
        headers=headers(outsider_token),
    ).status_code == 403

    cross_channel = study_group_client.get(
        f"/api/v1/study-groups/{group_id}/channels/"
        f"{second_channel['id']}/messages/{message_id}",
        headers=headers(owner_token),
    )
    assert cross_channel.status_code == 404

    forbidden_edit = study_group_client.put(
        f"/api/v1/study-groups/{group_id}/channels/"
        f"{first_channel['id']}/messages/{message_id}",
        headers=headers(owner_token),
        json={"content": "Owner rewrite"},
    )
    assert forbidden_edit.status_code == 403
    assert forbidden_edit.json()["error"]["code"] == (
        "STUDY_GROUP_MESSAGE_PERMISSION_DENIED"
    )

    updated = study_group_client.put(
        f"/api/v1/study-groups/{group_id}/channels/"
        f"{first_channel['id']}/messages/{message_id}",
        headers=headers(author_token),
        json={
            "content": "Updated by the author",
            "mentioned_user_ids": [owner_id],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["edited_at"] is not None
    assert updated.json()["mentioned_user_ids"] == [owner_id]

    deleted = study_group_client.delete(
        f"/api/v1/study-groups/{group_id}/channels/"
        f"{first_channel['id']}/messages/{message_id}",
        headers=headers(author_token),
    )
    assert deleted.status_code == 204
    assert study_group_client.get(
        f"/api/v1/study-groups/{group_id}/channels/"
        f"{first_channel['id']}/messages/{message_id}",
        headers=headers(owner_token),
    ).status_code == 404


@pytest.mark.asyncio
async def test_group_ai_mode_returns_grounded_companion_response(
    group_ai_context,
) -> None:
    """Verify explicit AI mode input and exact-channel ready-chunk scoping."""

    client = group_ai_context.client
    token = register_and_login(client, "group-ai-owner@example.com")
    group = client.post(
        "/api/v1/study-groups",
        headers=headers(token),
        json={
            "name": "Companion API group",
            "description": None,
            "visibility": "public",
            "max_members": 5,
        },
    ).json()
    channel = client.post(
        f"/api/v1/study-groups/{group['id']}/channels",
        headers=headers(token),
        json={"name": "Companion channel", "description": None},
    ).json()
    endpoint = (
        f"/api/v1/study-groups/{group['id']}/channels/"
        f"{channel['id']}/messages"
    )

    no_chunks = client.post(
        endpoint,
        headers=headers(token),
        json={"content": "Create a quiz", "ai_mode": "quiz"},
    )
    assert no_chunks.status_code == 409
    assert no_chunks.json()["error"]["code"] == (
        "STUDY_GROUP_NO_READY_CHUNKS"
    )

    await group_ai_context.chunk_repository.replace_channel_chunks(
        group_id=group["id"],
        channel_id=channel["id"],
        chunks=(
            GroundingChunk(
                content="Gradient descent updates parameters iteratively.",
                source=ChatSource(
                    note_id=1,
                    note_title="Channel lecture",
                    chunk_id=1,
                    page=2,
                ),
            ),
        ),
    )
    created = client.post(
        endpoint,
        headers=headers(token),
        json={
            "content": "Summarize gradient descent",
            "ai_mode": "summarizer",
            "response_format": "bullet_points",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["ai_mode_used"] == "summarizer"
    assert body["ai_response"]["mode"] == "summarizer"
    assert body["ai_response"]["sources"][0]["note_id"] == 1


def test_group_websocket_authentication_scope_and_message_delivery(
    study_group_client,
) -> None:
    """Deliver committed events only through a member's single-use ticket."""

    owner_token = register_and_login(
        study_group_client, "socket-owner@example.com"
    )
    member_token = register_and_login(
        study_group_client, "socket-member@example.com"
    )
    outsider_token = register_and_login(
        study_group_client, "socket-outsider@example.com"
    )
    group = study_group_client.post(
        "/api/v1/study-groups",
        headers=headers(owner_token),
        json={
            "name": "Socket group",
            "description": None,
            "visibility": "public",
            "max_members": 5,
        },
    ).json()
    assert study_group_client.post(
        f"/api/v1/study-groups/{group['id']}/join",
        headers=headers(member_token),
    ).status_code == 201
    channel = study_group_client.post(
        f"/api/v1/study-groups/{group['id']}/channels",
        headers=headers(owner_token),
        json={"name": "Live channel", "description": None},
    ).json()
    socket_path = (
        f"/api/v1/ws/study-groups/{group['id']}/channels/{channel['id']}"
    )

    ticket_response = study_group_client.post(
        "/api/v1/auth/websocket-ticket",
        headers=headers(owner_token),
    )
    ticket = ticket_response.json()["ticket"]
    with study_group_client.websocket_connect(
        f"{socket_path}?ticket={ticket}"
    ) as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "study_group.connection.ready"

        created = study_group_client.post(
            f"/api/v1/study-groups/{group['id']}/channels/"
            f"{channel['id']}/messages",
            headers=headers(member_token),
            json={"content": "Live message"},
        )
        assert created.status_code == 201
        event = websocket.receive_json()
        assert event["type"] == "study_group.message.created"
        assert event["data"]["id"] == created.json()["id"]

        updated = study_group_client.put(
            f"/api/v1/study-groups/{group['id']}/channels/"
            f"{channel['id']}/messages/{created.json()['id']}",
            headers=headers(member_token),
            json={"content": "Updated live message"},
        )
        assert updated.status_code == 200
        update_event = websocket.receive_json()
        assert update_event["type"] == "study_group.message.updated"

        deleted = study_group_client.delete(
            f"/api/v1/study-groups/{group['id']}/channels/"
            f"{channel['id']}/messages/{created.json()['id']}",
            headers=headers(member_token),
        )
        assert deleted.status_code == 204
        delete_event = websocket.receive_json()
        assert delete_event["type"] == "study_group.message.deleted"

        websocket.send_json({"type": "ping"})
        assert websocket.receive_json()["type"] == "pong"

    with pytest.raises(WebSocketDisconnect) as reused:
        with study_group_client.websocket_connect(
            f"{socket_path}?ticket={ticket}"
        ):
            pass
    assert reused.value.code == 4401

    outsider_ticket = study_group_client.post(
        "/api/v1/auth/websocket-ticket",
        headers=headers(outsider_token),
    ).json()["ticket"]
    with pytest.raises(WebSocketDisconnect) as forbidden:
        with study_group_client.websocket_connect(
            f"{socket_path}?ticket={outsider_ticket}"
        ):
            pass
    assert forbidden.value.code == 4403


@pytest.mark.asyncio
async def test_owner_adds_lists_and_removes_private_group_member(
    member_management_context,
) -> None:
    """Verify owner-managed membership and private member visibility."""

    client = member_management_context.client
    repository = member_management_context.repository
    owner_token, owner_id = register_login_and_get_id(
        client, "managed-owner@example.com"
    )
    member_token, member_id = register_login_and_get_id(
        client, "managed-member@example.com"
    )
    await repository.seed_user(
        user_id=owner_id,
        full_name="Managed Owner",
        email="managed-owner@example.com",
    )
    await repository.seed_user(
        user_id=member_id,
        full_name="Managed Member",
        email="managed-member@example.com",
    )

    created = client.post(
        "/api/v1/study-groups",
        headers=headers(owner_token),
        json={
            "name": "Managed private group",
            "description": None,
            "visibility": "private",
            "max_members": 5,
        },
    )
    group_id = created.json()["id"]

    added = client.post(
        f"/api/v1/study-groups/{group_id}/members",
        headers=headers(owner_token),
        json={"email": "MANAGED-MEMBER@example.com"},
    )
    assert added.status_code == 201
    assert added.json()["user_id"] == member_id

    member_list = client.get(
        f"/api/v1/study-groups/{group_id}/members",
        headers=headers(member_token),
    )
    assert member_list.status_code == 200
    assert member_list.json()["total"] == 2
    assert member_list.json()["items"][1]["full_name"] == "Managed Member"

    cannot_remove_owner = client.delete(
        f"/api/v1/study-groups/{group_id}/members/{owner_id}",
        headers=headers(owner_token),
    )
    assert cannot_remove_owner.status_code == 403

    removed = client.delete(
        f"/api/v1/study-groups/{group_id}/members/{member_id}",
        headers=headers(owner_token),
    )
    assert removed.status_code == 204
    assert client.get(
        f"/api/v1/study-groups/{group_id}/members",
        headers=headers(member_token),
    ).status_code == 404
