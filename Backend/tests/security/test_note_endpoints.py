"""Security and contract tests for authenticated Notes endpoints."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_auth_service, get_note_service
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
from app.domains.notes.application.services import NoteService
from app.domains.notes.infrastructure.local_storage import (
    LocalAttachmentStorage,
)
from app.domains.notes.infrastructure.memory_processing import (
    InMemoryAttachmentProcessingDispatcher,
)
from app.domains.notes.infrastructure.memory_repository import (
    InMemoryAttachmentRepository,
)
from app.main import app


@pytest.fixture
def note_client(tmp_path: Path) -> Iterator[TestClient]:
    """Provide isolated authentication, metadata, and storage adapters."""

    auth_service = AuthService(
        repository=InMemoryAuthRepository(),
        ticket_store=InMemoryWebSocketTicketStore(),
        revocation_store=InMemoryAccessTokenRevocationStore(),
    )
    note_service = NoteService(
        repository=InMemoryAttachmentRepository(),
        storage=LocalAttachmentStorage(tmp_path),
        processing_dispatcher=InMemoryAttachmentProcessingDispatcher(),
        maximum_file_size_bytes=1024,
    )

    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[get_note_service] = lambda: note_service

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def register_and_login(
    client: TestClient,
    *,
    email: str,
) -> str:
    """Create a student and return a bearer access token."""

    registration = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Notes Student",
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
    return login.json()["access_token"]


def authorization(token: str) -> dict[str, str]:
    """Build an HTTP bearer authorization header."""

    return {"Authorization": f"Bearer {token}"}


def upload_note(client: TestClient, token: str) -> dict:
    """Upload one valid PDF and return its public response."""

    response = client.post(
        "/api/v1/notes/upload",
        headers=authorization(token),
        data={"title": "Database Indexing"},
        files={
            "file": (
                "database-indexing.pdf",
                b"%PDF-1.7\nindexing notes",
                "application/pdf",
            )
        },
    )
    assert response.status_code == 202
    return response.json()


def test_note_upload_requires_authentication(note_client: TestClient) -> None:
    response = note_client.post(
        "/api/v1/notes/upload",
        files={
            "file": ("note.pdf", b"%PDF-1.7\nnote", "application/pdf")
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_upload_list_get_status_and_delete(note_client: TestClient) -> None:
    token = register_and_login(note_client, email="owner@example.com")
    uploaded = upload_note(note_client, token)

    assert uploaded["title"] == "Database Indexing"
    assert uploaded["status"] == "queued"
    assert uploaded["processing_progress"] == 0
    assert "object_path" not in uploaded
    assert "uploaded_by" not in uploaded

    listed = note_client.get(
        "/api/v1/notes",
        headers=authorization(token),
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == uploaded["id"]

    details = note_client.get(
        f"/api/v1/notes/{uploaded['id']}",
        headers=authorization(token),
    )
    assert details.status_code == 200
    assert details.json()["id"] == uploaded["id"]

    processing = note_client.get(
        f"/api/v1/notes/{uploaded['id']}/status",
        headers=authorization(token),
    )
    assert processing.status_code == 200
    assert processing.json()["status"] == "queued"

    deleted = note_client.delete(
        f"/api/v1/notes/{uploaded['id']}",
        headers=authorization(token),
    )
    assert deleted.status_code == 204

    missing = note_client.get(
        f"/api/v1/notes/{uploaded['id']}",
        headers=authorization(token),
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOTE_NOT_FOUND"


def test_student_cannot_access_another_students_note(
    note_client: TestClient,
) -> None:
    owner_token = register_and_login(
        note_client,
        email="first@example.com",
    )
    other_token = register_and_login(
        note_client,
        email="second@example.com",
    )
    uploaded = upload_note(note_client, owner_token)

    response = note_client.get(
        f"/api/v1/notes/{uploaded['id']}",
        headers=authorization(other_token),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOTE_NOT_FOUND"


@pytest.mark.parametrize(
    ("filename", "content", "content_type", "expected_code"),
    [
        ("note.txt", b"text", "text/plain", "UNSUPPORTED_FILE_TYPE"),
        ("note.pdf", b"", "application/pdf", "EMPTY_FILE"),
        ("note.pdf", b"not a pdf", "application/pdf", "INVALID_PDF"),
    ],
)
def test_invalid_uploads_use_shared_error_contract(
    note_client: TestClient,
    filename: str,
    content: bytes,
    content_type: str,
    expected_code: str,
) -> None:
    token = register_and_login(note_client, email="validation@example.com")

    response = note_client.post(
        "/api/v1/notes/upload",
        headers=authorization(token),
        files={"file": (filename, content, content_type)},
    )

    assert response.status_code in {415, 422}
    assert response.json()["error"]["code"] == expected_code
