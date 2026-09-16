"""End-to-end API test for the temporary local note-to-chat demo path."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_auth_service, get_chat_service, get_note_service
from app.domains.auth.application.services import AuthService
from app.domains.auth.infrastructure.memory_repository import InMemoryAuthRepository
from app.domains.auth.infrastructure.memory_revocation_store import (
    InMemoryAccessTokenRevocationStore,
)
from app.domains.auth.infrastructure.memory_ticket_store import (
    InMemoryWebSocketTicketStore,
)
from app.domains.chats.application.services import ChatService
from app.domains.chats.infrastructure.memory_answering import LocalGroundedAnswerGenerator
from app.domains.chats.infrastructure.memory_repository import InMemoryChatRepository
from app.domains.chats.infrastructure.memory_retrieval import (
    InMemoryReadyNoteChunkRepository,
)
from app.domains.notes.application.services import NoteService
from app.domains.notes.infrastructure.demo_processing import (
    SynchronousDemoAttachmentProcessingDispatcher,
)
from app.domains.notes.infrastructure.local_storage import LocalAttachmentStorage
from app.domains.notes.infrastructure.memory_repository import (
    InMemoryAttachmentRepository,
)
from app.main import app


@pytest.fixture
def demo_client(tmp_path: Path) -> Iterator[TestClient]:
    """Build an isolated application using shared in-memory demo adapters."""

    auth_service = AuthService(
        repository=InMemoryAuthRepository(),
        ticket_store=InMemoryWebSocketTicketStore(),
        revocation_store=InMemoryAccessTokenRevocationStore(),
    )
    attachment_repository = InMemoryAttachmentRepository()
    chunk_repository = InMemoryReadyNoteChunkRepository()

    def extract_demo_pages(_object_path: str) -> tuple[tuple[int, str], ...]:
        return (
            (
                1,
                "Bioethanol is a renewable liquid fuel commonly produced by "
                "fermenting sugars from plant biomass.",
            ),
        )

    dispatcher = SynchronousDemoAttachmentProcessingDispatcher(
        attachment_repository=attachment_repository,
        chunk_repository=chunk_repository,
        page_extractor=extract_demo_pages,
    )
    note_service = NoteService(
        repository=attachment_repository,
        storage=LocalAttachmentStorage(root_directory=tmp_path / "uploads"),
        processing_dispatcher=dispatcher,
        maximum_file_size_bytes=1024 * 1024,
    )
    chat_service = ChatService(
        repository=InMemoryChatRepository(),
        chunk_repository=chunk_repository,
        answer_generator=LocalGroundedAnswerGenerator(),
        maximum_question_length=4000,
    )

    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[get_note_service] = lambda: note_service
    app.dependency_overrides[get_chat_service] = lambda: chat_service

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def test_register_upload_and_ask_question_works_locally(demo_client: TestClient) -> None:
    """A student can complete the sponsor-demo workflow without PostgreSQL or RAG."""

    register_response = demo_client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Demo Student",
            "email": "demo.student@example.com",
            "password": "StrongPassword123!",
        },
    )
    assert register_response.status_code == 201

    login_response = demo_client.post(
        "/api/v1/auth/login",
        json={
            "email": "demo.student@example.com",
            "password": "StrongPassword123!",
        },
    )
    assert login_response.status_code == 200
    authorization = {
        "Authorization": f"Bearer {login_response.json()['access_token']}"
    }

    upload_response = demo_client.post(
        "/api/v1/notes/upload",
        headers=authorization,
        data={"title": "Bioethanol lecture"},
        files={"file": ("bioethanol.pdf", b"%PDF-1.4 demo", "application/pdf")},
    )
    assert upload_response.status_code == 202
    uploaded_note = upload_response.json()
    assert uploaded_note["status"] == "ready"
    assert uploaded_note["processing_progress"] == 100

    chat_response = demo_client.post(
        "/api/v1/chats",
        headers=authorization,
        json={"title": "Bioethanol questions"},
    )
    assert chat_response.status_code == 201
    chat_id = chat_response.json()["id"]

    answer_response = demo_client.post(
        f"/api/v1/chats/{chat_id}/messages",
        headers=authorization,
        json={"content": "What is bioethanol?"},
    )
    assert answer_response.status_code == 201
    answer = answer_response.json()["assistant_message"]
    assert "renewable liquid fuel" in answer["content"]
    assert answer["sources"][0]["note_id"] == uploaded_note["id"]
