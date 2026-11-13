"""HTTP contract tests for institutional registration and verification."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_auth_service
from app.domains.auth.application.email_verification import EmailVerificationService
from app.domains.auth.application.services import AuthService
from app.domains.auth.infrastructure.memory_email_verification import (
    InMemoryEmailVerificationRepository,
    InMemoryVerificationEmailSender,
)
from app.domains.auth.infrastructure.memory_repository import InMemoryAuthRepository
from app.domains.auth.infrastructure.memory_revocation_store import (
    InMemoryAccessTokenRevocationStore,
)
from app.domains.auth.infrastructure.memory_session_store import (
    InMemoryRefreshSessionStore,
)
from app.domains.auth.infrastructure.memory_ticket_store import (
    InMemoryWebSocketTicketStore,
)
from app.main import app


@pytest.fixture
def institutional_client() -> Iterator[tuple[TestClient, InMemoryVerificationEmailSender]]:
    auth_repository = InMemoryAuthRepository()
    sender = InMemoryVerificationEmailSender()
    verification = EmailVerificationService(
        repository=InMemoryEmailVerificationRepository(auth_repository),
        sender=sender,
        secret="endpoint-test-secret-with-more-than-32-bytes",
        ttl_minutes=10,
        max_attempts=5,
        resend_cooldown_seconds=60,
    )
    service = AuthService(
        repository=auth_repository,
        ticket_store=InMemoryWebSocketTicketStore(),
        revocation_store=InMemoryAccessTokenRevocationStore(),
        session_store=InMemoryRefreshSessionStore(),
        email_verification_service=verification,
        institutional_email_restriction_enabled=True,
        email_verification_required=True,
    )
    app.dependency_overrides[get_auth_service] = lambda: service
    client = TestClient(app)
    try:
        yield client, sender
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_student_registration_verification_and_login(
    institutional_client,
) -> None:
    client, sender = institutional_client
    email = "c1234567@uon.edu.au"
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "UON Student",
            "email": email,
            "password": "SecurePassword123!",
        },
    )
    assert registered.status_code == 201
    assert registered.json()["verification_required"] is True

    blocked = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePassword123!"},
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"

    confirmed = client.post(
        "/api/v1/auth/email-verification/confirm",
        json={"email": email, "code": sender.latest_code_for(email)},
    )
    assert confirmed.status_code == 200
    assert confirmed.json() == {"email": email, "verified": True}
    assert client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePassword123!"},
    ).status_code == 200


@pytest.mark.parametrize(
    "email",
    [
        "student@gmail.com",
        "student@newcastle.edu.au",
        "student@uon.edu.au.attacker.example",
    ],
)
def test_public_registration_rejects_non_student_domains(
    institutional_client,
    email: str,
) -> None:
    client, _ = institutional_client
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Invalid Student",
            "email": email,
            "password": "SecurePassword123!",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INSTITUTIONAL_EMAIL_REQUIRED"


def test_resend_is_rate_limited(institutional_client) -> None:
    client, _ = institutional_client
    email = "firstname.lastname@uon.edu.au"
    assert client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Named Student",
            "email": email,
            "password": "SecurePassword123!",
        },
    ).status_code == 201
    response = client.post(
        "/api/v1/auth/email-verification/resend",
        json={"email": email},
    )
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "VERIFICATION_RESEND_TOO_SOON"
