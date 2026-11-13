"""
Authentication application use cases.

This service coordinates password security, tokens and repository operations.
It does not contain HTTP responses or SQL.
"""
from datetime import datetime, timezone

from app.core.config import settings
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    hash_password,
    verify_password,
)
from app.domains.auth.domain.exceptions import (
    CurrentPasswordIncorrectError,
    EmailAlreadyRegisteredError,
    EmailNotVerifiedError,
    InactiveAccountError,
    InvalidCredentialsError,
    InvalidSessionError,
    InvalidVerificationCodeError,
    PasswordReuseError,
)
from app.domains.auth.application.email_verification import EmailVerificationService
from app.domains.auth.domain.email_policy import normalize_email, require_approved_email
from app.domains.auth.domain.models import (
    AuthSession,
    User,
    WebSocketTicket,
)
from app.domains.auth.domain.repository import AuthRepository
from app.domains.auth.domain.password_repository import PasswordChangeRepository
from app.domains.auth.domain.revocation_store import (
    AccessTokenRevocationStore,
)
from app.domains.auth.domain.session_store import RefreshSessionStore
from app.domains.auth.domain.ticket_store import WebSocketTicketStore


class AuthService:
    """Coordinate authentication use cases through abstract storage contracts."""

    def __init__(
        self,
        repository: AuthRepository,
        ticket_store: WebSocketTicketStore,
        revocation_store: AccessTokenRevocationStore,
        session_store: RefreshSessionStore,
        email_verification_service: EmailVerificationService | None = None,
        institutional_email_restriction_enabled: bool = False,
        institutional_email_allowlist: set[str] | None = None,
        email_verification_required: bool = False,
    ) -> None:
        """Initialize the service with repository, ticket, and revocation stores."""

        self.repository = repository
        self.ticket_store = ticket_store
        self.revocation_store = revocation_store
        self.session_store = session_store
        self.email_verification_service = email_verification_service
        self.institutional_email_restriction_enabled = (
            institutional_email_restriction_enabled
        )
        self.institutional_email_allowlist = institutional_email_allowlist or set()
        self.email_verification_required = email_verification_required

    async def register(
        self,
        full_name: str,
        email: str,
        password: str,
    ) -> User:
        """Register a normalized account using a securely hashed password.

        Raises:
            EmailAlreadyRegisteredError: If the normalized email already exists.
        """

        # Emails are case-insensitive for authentication.
        normalized_email = normalize_email(email)
        if self.institutional_email_restriction_enabled:
            normalized_email = require_approved_email(
                normalized_email,
                role="student",
                allowlist=self.institutional_email_allowlist,
            )
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

        user = await self.repository.create_user(
            full_name=normalized_name,
            email=normalized_email,
            hashed_password=hashed_password,
            email_verified_at=None
            if self.email_verification_required
            else datetime.now(timezone.utc),
        )
        if self.email_verification_required:
            if self.email_verification_service is None:
                raise RuntimeError("Email verification service is not configured")
            await self.email_verification_service.issue(
                user_id=user.id,
                email=user.email,
            )
        return user

    async def confirm_email_verification(self, *, email: str, code: str) -> User:
        """Verify one account email and return its safe account record."""

        if self.email_verification_service is None:
            raise RuntimeError("Email verification service is not configured")
        normalized_email = normalize_email(email)
        await self.email_verification_service.confirm(
            email=normalized_email,
            code=code,
        )
        credentials = await self.repository.get_credentials_by_email(
            normalized_email
        )
        if credentials is None:
            raise InvalidVerificationCodeError("The verification code is invalid.")
        return credentials.user

    async def resend_email_verification(self, *, email: str) -> None:
        """Send a replacement code when an existing account is unverified."""

        if self.email_verification_service is None:
            raise RuntimeError("Email verification service is not configured")
        normalized_email = normalize_email(email)
        credentials = await self.repository.get_credentials_by_email(
            normalized_email
        )
        # Keep the HTTP response generic for unknown and already-verified emails.
        if credentials is None or credentials.user.is_email_verified:
            return
        await self.email_verification_service.issue(
            user_id=credentials.user.id,
            email=credentials.user.email,
            enforce_cooldown=True,
        )

    async def login(
        self,
        email: str,
        password: str,
    ) -> AuthSession:
        """Validate credentials and create a signed access-token session.

        Raises:
            InvalidCredentialsError: If the email or password is incorrect.
            InactiveAccountError: If the matched account is disabled.
        """

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

        if (
            self.email_verification_required
            and not credentials.user.is_email_verified
        ):
            raise EmailNotVerifiedError(
                "Please verify your university email before signing in."
            )

        access_token = create_access_token(
            subject=credentials.user.id,
        )
        refresh_token = await self.session_store.create(
            credentials.user.id,
            idle_timeout_seconds=60 * settings.SESSION_IDLE_TIMEOUT_MINUTES,
            absolute_timeout_seconds=(
                60 * 60 * settings.SESSION_ABSOLUTE_TIMEOUT_HOURS
            ),
        )

        return AuthSession(
            access_token=access_token,
            token_type="bearer",
            expires_in=60 * settings.ACCESS_TOKEN_EXPIRE_MINUTES,
            user=credentials.user,
            refresh_token=refresh_token,
        )

    async def refresh(self, refresh_token: str) -> AuthSession:
        """Renew an access token while the browser session remains active."""

        refresh_session = await self.session_store.resolve_and_touch(
            refresh_token,
            idle_timeout_seconds=60 * settings.SESSION_IDLE_TIMEOUT_MINUTES,
        )
        if refresh_session is None:
            raise InvalidSessionError(
                "The session is missing, expired, or inactive."
            )

        user = await self.repository.get_user_by_id(refresh_session.user_id)
        if (
            user is None
            or not user.is_active
            or (
                self.email_verification_required
                and not user.is_email_verified
            )
        ):
            await self.session_store.revoke(refresh_token)
            raise InvalidSessionError(
                "The session is missing, expired, or inactive."
            )

        access_token = create_access_token(subject=user.id)
        return AuthSession(
            access_token=access_token,
            token_type="bearer",
            expires_in=60 * settings.ACCESS_TOKEN_EXPIRE_MINUTES,
            user=user,
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

    async def consume_websocket_ticket(
        self,
        ticket: str,
    ) -> str | None:
        """Consume a single-use ticket and return its authenticated user ID."""

        return await self.ticket_store.consume(ticket)

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

    async def revoke_refresh_session(self, refresh_token: str) -> None:
        """End the server-managed browser session represented by a cookie."""

        await self.session_store.revoke(refresh_token)


class PasswordChangeService:
    """Verify and replace the authenticated user's password hash."""

    def __init__(self, repository: PasswordChangeRepository) -> None:
        self.repository = repository

    async def change_password(
        self,
        *,
        user_id: str,
        current_password: str,
        new_password: str,
    ) -> None:
        current_hash = await self.repository.get_password_hash(user_id)
        if current_hash is None or not verify_password(current_password, current_hash):
            raise CurrentPasswordIncorrectError("The current password is incorrect.")
        if verify_password(new_password, current_hash):
            raise PasswordReuseError(
                "The new password must be different from the current password."
            )
        updated = await self.repository.update_password_hash(
            user_id=user_id,
            password_hash=hash_password(new_password),
        )
        if not updated:
            raise CurrentPasswordIncorrectError("The account is unavailable.")
