"""
Authentication application use cases.

This service coordinates password security, tokens and repository operations.
It does not contain HTTP responses or SQL.
"""
from datetime import datetime

from app.core.config import settings
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    hash_password,
    verify_password,
)
from app.domains.auth.domain.exceptions import (
    EmailAlreadyRegisteredError,
    InactiveAccountError,
    InvalidCredentialsError,
)
from app.domains.auth.domain.models import (
    AuthSession,
    User,
    WebSocketTicket,
)
from app.domains.auth.domain.repository import AuthRepository
from app.domains.auth.domain.revocation_store import (
    AccessTokenRevocationStore,
)
from app.domains.auth.domain.ticket_store import WebSocketTicketStore


class AuthService:

    def __init__(
        self,
        repository: AuthRepository,
        ticket_store: WebSocketTicketStore,
        revocation_store: AccessTokenRevocationStore,
    ) -> None:
        self.repository = repository
        self.ticket_store = ticket_store
        self.revocation_store = revocation_store

    async def register(
        self,
        full_name: str,
        email: str,
        password: str,
    ) -> User:
        # Emails are case-insensitive for authentication.
        normalized_email = email.strip().lower()
        normalized_name = full_name.strip()

        existing_user = await self.repository.get_credentials_by_email(
            normalized_email
        )

        if existing_user is not None:
            raise EmailAlreadyRegisteredError(
                "An account with this email already exists."
            )

        # Only the hash is passed to the repository.
        hashed_password = hash_password(password)

        return await self.repository.create_user(
            full_name=normalized_name,
            email=normalized_email,
            hashed_password=hashed_password,
        )

    async def login(
        self,
        email: str,
        password: str,
    ) -> AuthSession:
        normalized_email = email.strip().lower()

        credentials = await self.repository.get_credentials_by_email(
            normalized_email
        )

        if credentials is None:
            # Perform a password check even when the account is absent.
            # This reduces email-enumeration timing differences.
            verify_password(
                password,
                DUMMY_PASSWORD_HASH,
            )

            raise InvalidCredentialsError(
                "Incorrect email or password."
            )

        if not verify_password(
            password,
            credentials.hashed_password,
        ):
            raise InvalidCredentialsError(
                "Incorrect email or password."
            )

        if not credentials.user.is_active:
            raise InactiveAccountError(
                "This account is inactive."
            )

        access_token = create_access_token(
            subject=credentials.user.id,
        )

        return AuthSession(
            access_token=access_token,
            token_type="bearer",
            expires_in=60 * settings.ACCESS_TOKEN_EXPIRE_MINUTES,
            user=credentials.user,
        )

    async def get_user(
        self,
        user_id: str,
    ) -> User | None:
        """Load the authenticated user represented by a valid JWT."""

        return await self.repository.get_user_by_id(user_id)

    async def issue_websocket_ticket(
        self,
        user_id: str,
    ) -> WebSocketTicket:
        """Create a short-lived ticket for an authenticated user."""

        expires_in = settings.WEBSOCKET_TICKET_EXPIRE_SECONDS
        ticket = await self.ticket_store.create(
            user_id=user_id,
            expires_in=expires_in,
        )

        return WebSocketTicket(
            ticket=ticket,
            expires_in=expires_in,
        )

    async def logout(
        self,
        token_id: str,
        expires_at: datetime,
    ) -> None:
        """Revoke the current access token for the rest of its lifetime."""

        await self.revocation_store.revoke(
            token_id=token_id,
            expires_at=expires_at,
        )

    async def is_access_token_revoked(self, token_id: str) -> bool:
        """Check whether a previously issued token has been logged out."""

        return await self.revocation_store.is_revoked(token_id)
