"""Unit tests for authentication application use cases."""

import asyncio

import pytest

from app.core.security import decode_access_token_claims
from app.domains.auth.application.services import AuthService
from app.domains.auth.domain.exceptions import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
)
from app.domains.auth.infrastructure.memory_repository import (
    InMemoryAuthRepository,
)
from app.domains.auth.infrastructure.memory_revocation_store import (
    InMemoryAccessTokenRevocationStore,
)
from app.domains.auth.infrastructure.memory_ticket_store import (
    InMemoryWebSocketTicketStore,
)


def create_service() -> tuple[
    AuthService,
    InMemoryAuthRepository,
    InMemoryWebSocketTicketStore,
]:
    """Construct an isolated authentication service using memory adapters."""

    repository = InMemoryAuthRepository()
    ticket_store = InMemoryWebSocketTicketStore()
    service = AuthService(
        repository=repository,
        ticket_store=ticket_store,
        revocation_store=InMemoryAccessTokenRevocationStore(),
    )
    return service, repository, ticket_store


def test_register_normalizes_identity_and_hashes_password() -> None:
    async def scenario() -> None:
        service, repository, _ = create_service()

        user = await service.register(
            full_name="  Example Student  ",
            email="STUDENT@EXAMPLE.COM",
            password="SecurePassword123!",
        )
        credentials = await repository.get_credentials_by_email(
            "student@example.com"
        )

        assert user.full_name == "Example Student"
        assert user.email == "student@example.com"
        assert credentials is not None
        assert credentials.hashed_password != "SecurePassword123!"

    asyncio.run(scenario())


def test_duplicate_registration_is_rejected() -> None:
    async def scenario() -> None:
        service, _, _ = create_service()

        await service.register(
            full_name="Example Student",
            email="student@example.com",
            password="SecurePassword123!",
        )

        with pytest.raises(EmailAlreadyRegisteredError):
            await service.register(
                full_name="Another Student",
                email="STUDENT@example.com",
                password="AnotherPassword123!",
            )

    asyncio.run(scenario())


def test_login_creates_token_and_rejects_wrong_password() -> None:
    async def scenario() -> None:
        service, _, _ = create_service()
        user = await service.register(
            full_name="Example Student",
            email="student@example.com",
            password="SecurePassword123!",
        )

        session = await service.login(
            email="student@example.com",
            password="SecurePassword123!",
        )
        claims = decode_access_token_claims(session.access_token)

        assert claims.subject == user.id
        assert session.user == user
        assert session.token_type == "bearer"

        with pytest.raises(InvalidCredentialsError):
            await service.login(
                email="student@example.com",
                password="incorrect-password",
            )

    asyncio.run(scenario())


def test_logout_revokes_only_the_supplied_token_identifier() -> None:
    async def scenario() -> None:
        service, _, _ = create_service()
        await service.register(
            full_name="Example Student",
            email="student@example.com",
            password="SecurePassword123!",
        )
        first_session = await service.login(
            email="student@example.com",
            password="SecurePassword123!",
        )
        second_session = await service.login(
            email="student@example.com",
            password="SecurePassword123!",
        )
        first_claims = decode_access_token_claims(
            first_session.access_token
        )
        second_claims = decode_access_token_claims(
            second_session.access_token
        )

        await service.logout(
            token_id=first_claims.token_id,
            expires_at=first_claims.expires_at,
        )

        assert await service.is_access_token_revoked(
            first_claims.token_id
        )
        assert not await service.is_access_token_revoked(
            second_claims.token_id
        )

    asyncio.run(scenario())


def test_websocket_ticket_is_created_and_consumed_once() -> None:
    async def scenario() -> None:
        service, _, ticket_store = create_service()

        result = await service.issue_websocket_ticket("student-123")

        assert result.expires_in == 60
        assert await ticket_store.consume(result.ticket) == "student-123"
        assert await ticket_store.consume(result.ticket) is None

    asyncio.run(scenario())
