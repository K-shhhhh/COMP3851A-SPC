"""Contract and security tests for the temporary local authentication flow."""

import asyncio
from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_auth_service
from app.core.security import create_access_token
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
from app.domains.auth.infrastructure.memory_session_store import (
    InMemoryRefreshSessionStore,
)
from app.main import app


@dataclass
class AuthTestContext:
    """Dependencies shared by one isolated authentication endpoint test."""

    client: TestClient
    ticket_store: InMemoryWebSocketTicketStore


@pytest.fixture
def auth_context() -> Iterator[AuthTestContext]:
    """Give each test isolated users and WebSocket tickets."""

    repository = InMemoryAuthRepository()
    ticket_store = InMemoryWebSocketTicketStore()
    service = AuthService(
        repository=repository,
        ticket_store=ticket_store,
        revocation_store=InMemoryAccessTokenRevocationStore(),
        session_store=InMemoryRefreshSessionStore(),
    )

    app.dependency_overrides[get_auth_service] = lambda: service

    # Dependencies are fully replaced with in-memory adapters, so this
    # contract test intentionally skips the PostgreSQL application lifespan.
    client = TestClient(app)
    try:
        yield AuthTestContext(
            client=client,
            ticket_store=ticket_store,
        )
    finally:
        client.close()

    app.dependency_overrides.clear()


def register_student(
    client: TestClient,
    *,
    email: str = "student@example.com",
) -> dict:
    """Register a student through the public API and return its response."""

    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Example Student",
            "email": email,
            "password": "SecurePassword123!",
        },
    )
    assert response.status_code == 201
    return response.json()


def login_student(
    client: TestClient,
    *,
    email: str = "student@example.com",
) -> dict:
    """Log in a student through the public API and return its response."""

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "SecurePassword123!",
        },
    )
    assert response.status_code == 200
    return response.json()


def test_register_login_and_get_current_user(
    auth_context: AuthTestContext,
) -> None:
    client = auth_context.client
    registered = register_student(client)
    login = login_student(client)

    response = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": f"Bearer {login['access_token']}",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": registered["id"],
        "full_name": registered["full_name"],
        "email": registered["email"],
        "role": "student",
    }
    assert "password" not in registered
    assert "created_at" not in login["user"]
    refresh_cookie = client.cookies.get("spc_refresh_session")
    assert refresh_cookie
    assert refresh_cookie not in login["access_token"]


def test_refresh_renews_access_for_an_active_browser_session(
    auth_context: AuthTestContext,
) -> None:
    client = auth_context.client
    register_student(client)
    login = login_student(client)

    refreshed = client.post("/api/v1/auth/refresh")

    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"] != login["access_token"]
    assert refreshed.json()["expires_in"] > 0


def test_refresh_rejects_a_missing_or_revoked_session(
    auth_context: AuthTestContext,
) -> None:
    client = auth_context.client

    missing = client.post("/api/v1/auth/refresh")
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "SESSION_REQUIRED"

    register_student(client)
    login_student(client)
    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 204

    expired = client.post("/api/v1/auth/refresh")
    assert expired.status_code == 401
    assert expired.json()["error"]["code"] == "SESSION_REQUIRED"


def test_duplicate_registration_and_invalid_login(
    auth_context: AuthTestContext,
) -> None:
    client = auth_context.client
    register_student(client)

    duplicate = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Duplicate Student",
            "email": "STUDENT@example.com",
            "password": "AnotherSecurePassword123!",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"

    invalid_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "student@example.com",
            "password": "incorrect-password",
        },
    )
    assert invalid_login.status_code == 401
    assert invalid_login.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_protected_endpoint_rejects_missing_and_expired_tokens(
    auth_context: AuthTestContext,
) -> None:
    client = auth_context.client
    registered = register_student(client)

    missing = client.get("/api/v1/auth/me")
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"

    expired_token = create_access_token(
        registered["id"],
        expires_minutes=-1,
    )
    expired = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": f"Bearer {expired_token}",
        },
    )
    assert expired.status_code == 401
    assert expired.json()["error"]["code"] == "TOKEN_EXPIRED"


def test_validation_errors_use_the_shared_error_contract(
    auth_context: AuthTestContext,
) -> None:
    response = auth_context.client.post(
        "/api/v1/auth/register",
        json={
            "full_name": " ",
            "email": "invalid-email",
            "password": "short",
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert payload["request_id"]
    assert len(payload["error"]["details"]["fields"]) == 3


def test_websocket_ticket_is_authenticated_and_single_use(
    auth_context: AuthTestContext,
) -> None:
    client = auth_context.client
    registered = register_student(client)
    login = login_student(client)

    missing_auth = client.post("/api/v1/auth/websocket-ticket")
    assert missing_auth.status_code == 401

    response = client.post(
        "/api/v1/auth/websocket-ticket",
        headers={
            "Authorization": f"Bearer {login['access_token']}",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["expires_in"] == 60

    first_consumption = asyncio.run(
        auth_context.ticket_store.consume(payload["ticket"])
    )
    second_consumption = asyncio.run(
        auth_context.ticket_store.consume(payload["ticket"])
    )

    assert first_consumption == registered["id"]
    assert second_consumption is None


def test_logout_revokes_only_the_current_access_token(
    auth_context: AuthTestContext,
) -> None:
    client = auth_context.client
    register_student(client)
    first_login = login_student(client)
    second_login = login_student(client)

    logout = client.post(
        "/api/v1/auth/logout",
        headers={
            "Authorization": f"Bearer {first_login['access_token']}",
        },
    )
    assert logout.status_code == 204
    assert logout.content == b""

    revoked = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": f"Bearer {first_login['access_token']}",
        },
    )
    assert revoked.status_code == 401
    assert revoked.json()["error"]["code"] == "TOKEN_REVOKED"

    still_valid = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": f"Bearer {second_login['access_token']}",
        },
    )
    assert still_valid.status_code == 200


def test_logout_requires_authentication(
    auth_context: AuthTestContext,
) -> None:
    response = auth_context.client.post("/api/v1/auth/logout")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
