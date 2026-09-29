"""Security and response-contract tests for knowledge-graph endpoints."""

import asyncio
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_auth_service,
    get_knowledge_graph_service,
)
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
from app.domains.knowledge_graph.application.services import (
    KnowledgeGraphService,
)
from app.domains.knowledge_graph.domain.models import KnowledgeNode
from app.domains.knowledge_graph.infrastructure.memory_repository import (
    InMemoryKnowledgeGraphRepository,
)
from app.domains.notes.domain.models import NoteProcessingStatus
from app.domains.notes.infrastructure.memory_repository import (
    InMemoryAttachmentRepository,
)
from app.main import app


@pytest.fixture
def graph_client() -> Iterator[tuple[TestClient, KnowledgeGraphService]]:
    """Provide isolated authentication, attachment, and graph adapters."""

    auth_service = AuthService(
        repository=InMemoryAuthRepository(),
        ticket_store=InMemoryWebSocketTicketStore(),
        revocation_store=InMemoryAccessTokenRevocationStore(),
    )
    graph_service = KnowledgeGraphService(
        repository=InMemoryKnowledgeGraphRepository(),
        attachment_repository=InMemoryAttachmentRepository(),
    )
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[get_knowledge_graph_service] = (
        lambda: graph_service
    )

    # Do not enter the application lifespan here: every persistence dependency
    # used by this test is overridden with an isolated in-memory adapter.
    client = TestClient(app)
    yield client, graph_service
    client.close()
    app.dependency_overrides.clear()


def register(client: TestClient, email: str) -> tuple[str, str]:
    """Register a student and return their identifier and access token."""

    registration = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Graph Student",
            "email": email,
            "password": "SecurePassword123!",
        },
    )
    assert registration.status_code == 201

    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "SecurePassword123!",
        },
    )
    assert login.status_code == 200
    return registration.json()["id"], login.json()["access_token"]


async def prepare_graph(
    service: KnowledgeGraphService,
    *,
    user_id: str,
) -> int:
    """Create a processed attachment and its graph in fixture storage."""

    attachments = service._attachment_repository
    attachment = await attachments.create_attachment(
        uploaded_by=user_id,
        title="Data Structures",
        file_name="data-structures.pdf",
        file_type="application/pdf",
        file_size_bytes=100,
        object_path="/private/data-structures.pdf",
    )
    await attachments.update_processing_status(
        attachment_id=attachment.attachment_id,
        processing_status=NoteProcessingStatus.READY,
        processing_progress=100,
    )
    await service.replace_graph_for_attachment(
        attachment_id=attachment.attachment_id,
        nodes=[
            KnowledgeNode(
                id=1,
                attachment_id=attachment.attachment_id,
                title="Binary Tree",
                topic="Data Structures",
                description="A tree with at most two children per node.",
                source_chunk_id=7,
            )
        ],
        edges=[],
    )
    return attachment.attachment_id


def test_graph_endpoint_requires_authentication(
    graph_client: tuple[TestClient, KnowledgeGraphService],
) -> None:
    client, _ = graph_client

    response = client.get("/api/v1/notes/1/knowledge-graph")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_owner_can_read_attachment_graph(
    graph_client: tuple[TestClient, KnowledgeGraphService],
) -> None:
    client, service = graph_client
    user_id, token = register(client, "graph-owner@example.com")
    attachment_id = asyncio.run(
        prepare_graph(service, user_id=user_id)
    )

    response = client.get(
        f"/api/v1/notes/{attachment_id}/knowledge-graph",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["attachment_id"] == attachment_id
    assert body["nodes"][0]["title"] == "Binary Tree"
    assert body["nodes"][0]["source_chunk_id"] == 7
    assert body["edges"] == []


def test_user_cannot_read_another_users_graph(
    graph_client: tuple[TestClient, KnowledgeGraphService],
) -> None:
    client, service = graph_client
    owner_id, _ = register(client, "first-graph-owner@example.com")
    _, other_token = register(client, "other-graph-user@example.com")
    attachment_id = asyncio.run(
        prepare_graph(service, user_id=owner_id)
    )

    response = client.get(
        f"/api/v1/notes/{attachment_id}/knowledge-graph",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOTE_NOT_FOUND"


def test_processed_note_without_graph_returns_not_ready(
    graph_client: tuple[TestClient, KnowledgeGraphService],
) -> None:
    client, service = graph_client
    user_id, token = register(client, "waiting-graph@example.com")
    attachments = service._attachment_repository

    async def create_processed_note() -> int:
        attachment = await attachments.create_attachment(
            uploaded_by=user_id,
            title="Waiting Graph",
            file_name="waiting.pdf",
            file_type="application/pdf",
            file_size_bytes=100,
            object_path="/private/waiting.pdf",
        )
        await attachments.update_processing_status(
            attachment_id=attachment.attachment_id,
            processing_status=NoteProcessingStatus.READY,
            processing_progress=100,
        )
        return attachment.attachment_id

    attachment_id = asyncio.run(create_processed_note())
    response = client.get(
        f"/api/v1/notes/{attachment_id}/knowledge-graph",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409
    assert (
        response.json()["error"]["code"]
        == "KNOWLEDGE_GRAPH_NOT_READY"
    )
