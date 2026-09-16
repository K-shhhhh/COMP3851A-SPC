"""Security and contract tests for personal Chat/Ask endpoints."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_auth_service, get_chat_service
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
from app.domains.chats.application.services import ChatService
from app.domains.chats.domain.models import ChatSource
from app.domains.chats.domain.retrieval import GroundingChunk
from app.domains.chats.infrastructure.memory_answering import (
    LocalGroundedAnswerGenerator,
)
from app.domains.chats.infrastructure.memory_repository import (
    InMemoryChatRepository,
)
from app.domains.chats.infrastructure.memory_retrieval import (
    InMemoryReadyNoteChunkRepository,
)
from app.main import app


@pytest.fixture
def chat_client() -> Iterator[tuple[TestClient, InMemoryReadyNoteChunkRepository]]:
    """Provide isolated auth, chat, retrieval, and answer adapters."""

    auth_service = AuthService(
        repository=InMemoryAuthRepository(),
        ticket_store=InMemoryWebSocketTicketStore(),
        revocation_store=InMemoryAccessTokenRevocationStore(),
    )
    chunks = InMemoryReadyNoteChunkRepository()
    chat_service = ChatService(
        repository=InMemoryChatRepository(),
        chunk_repository=chunks,
        answer_generator=LocalGroundedAnswerGenerator(),
        maximum_question_length=4000,
    )

    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[get_chat_service] = lambda: chat_service

    with TestClient(app) as client:
        yield client, chunks

    app.dependency_overrides.clear()


def register_and_login(
    client: TestClient,
    *,
    email: str,
) -> tuple[str, str]:
    """Create one student and return its token and public identifier."""

    registration = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Chat Student",
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
    return login.json()["access_token"], registration.json()["id"]


def authorization(token: str) -> dict[str, str]:
    """Build an HTTP bearer authorization header."""

    return {"Authorization": f"Bearer {token}"}


async def seed_ready_chunk(
    chunks: InMemoryReadyNoteChunkRepository,
    *,
    user_id: str,
) -> None:
    """Provide one ready and authorized chunk to the test user."""

    await chunks.replace_user_chunks(
        user_id=user_id,
        chunks=(
            GroundingChunk(
                content="A database index speeds up selected lookups.",
                source=ChatSource(
                    note_id=1,
                    note_title="Database Notes",
                    chunk_id=5,
                    page=2,
                ),
            ),
        ),
    )


def test_chat_creation_requires_authentication(
    chat_client,
) -> None:
    """Reject anonymous conversation creation."""

    client, _ = chat_client
    response = client.post("/api/v1/chats", json={"title": None})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


@pytest.mark.asyncio
async def test_personal_chat_crud_and_synchronous_answer(
    chat_client,
) -> None:
    """Verify the full local conversation and grounded-answer contract."""

    client, chunks = chat_client
    token, user_id = register_and_login(client, email="chat@example.com")
    headers = authorization(token)

    created = client.post(
        "/api/v1/chats",
        headers=headers,
        json={"title": None},
    )
    assert created.status_code == 201
    chat_id = created.json()["id"]

    unavailable = client.post(
        f"/api/v1/chats/{chat_id}/messages",
        headers=headers,
        json={"content": "What is an index?"},
    )
    assert unavailable.status_code == 409
    assert unavailable.json()["error"]["code"] == "NO_PROCESSED_NOTES"

    await seed_ready_chunk(chunks, user_id=user_id)
    answered = client.post(
        f"/api/v1/chats/{chat_id}/messages",
        headers=headers,
        json={"content": "What is an index?"},
    )
    assert answered.status_code == 201
    assert answered.json()["assistant_message"]["sources"][0]["chunk_id"] == 5

    history = client.get(
        f"/api/v1/chats/{chat_id}/messages",
        headers=headers,
    )
    assert history.status_code == 200
    assert history.json()["total"] == 2

    renamed = client.patch(
        f"/api/v1/chats/{chat_id}",
        headers=headers,
        json={"title": "Indexing questions"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Indexing questions"

    deleted = client.delete(f"/api/v1/chats/{chat_id}", headers=headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/chats/{chat_id}", headers=headers).status_code == 404


def test_student_cannot_access_another_students_chat(chat_client) -> None:
    """Hide another student's chat across every protected operation."""

    client, _ = chat_client
    owner_token, _ = register_and_login(client, email="owner-chat@example.com")
    other_token, _ = register_and_login(client, email="other-chat@example.com")
    created = client.post(
        "/api/v1/chats",
        headers=authorization(owner_token),
        json={"title": "Private conversation"},
    )
    chat_id = created.json()["id"]
    other_headers = authorization(other_token)

    responses = [
        client.get(f"/api/v1/chats/{chat_id}", headers=other_headers),
        client.get(
            f"/api/v1/chats/{chat_id}/messages",
            headers=other_headers,
        ),
        client.post(
            f"/api/v1/chats/{chat_id}/messages",
            headers=other_headers,
            json={"content": "Show me the owner's notes"},
        ),
        client.delete(f"/api/v1/chats/{chat_id}", headers=other_headers),
    ]

    assert all(response.status_code == 404 for response in responses)
    assert all(
        response.json()["error"]["code"] == "CHAT_NOT_FOUND"
        for response in responses
    )


def test_whitespace_question_uses_shared_validation_error(chat_client) -> None:
    """Reject content that becomes empty after normalization."""

    client, _ = chat_client
    token, _ = register_and_login(client, email="validation-chat@example.com")
    headers = authorization(token)
    created = client.post(
        "/api/v1/chats",
        headers=headers,
        json={"title": None},
    )

    response = client.post(
        f"/api/v1/chats/{created.json()['id']}/messages",
        headers=headers,
        json={"content": "   "},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"

