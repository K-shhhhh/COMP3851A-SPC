"""Construct application services and enforce request authentication.

This module is the backend composition boundary. It currently injects local
in-memory authentication stores; staging must select PostgreSQL and Redis
implementations when those integrations are ready.
"""
from collections.abc import Callable

from fastapi import Depends, Security
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from app.api.error_handlers import ApiError
from app.core.security import (
    AccessTokenClaims,
    AccessTokenError,
    AccessTokenExpiredError,
    decode_access_token_claims,
)
from app.domains.auth.domain.models import User

from app.domains.auth.application.services import AuthService
from app.domains.auth.domain.repository import AuthRepository
from app.domains.auth.infrastructure.memory_repository import (
    InMemoryAuthRepository,
)
from app.domains.auth.infrastructure.memory_revocation_store import (
    InMemoryAccessTokenRevocationStore,
)
from app.domains.auth.infrastructure.memory_ticket_store import (
    InMemoryWebSocketTicketStore,
)
from app.domains.users.application.services import UserService
from app.domains.users.domain.repository import UserRepository
from app.domains.users.infrastructure.repository import PostgreSQLUserRepository

from app.domains.notes.application.services import NoteService
from app.domains.notes.domain.repository import NoteRepository
from app.domains.notes.infrastructure.repository import PostgreSQLNoteRepository

from app.domains.study_groups.application.services import StudyGroupService
from app.domains.study_groups.domain.repository import StudyGroupRepository
from app.domains.study_groups.infrastructure.repository import PostgreSQLStudyGroupRepository

from app.domains.knowledge_graph.application.services import KnowledgeGraphService
from app.domains.knowledge_graph.domain.repository import KnowledgeGraphRepository
from app.domains.knowledge_graph.infrastructure.repository import PostgreSQLKnowledgeGraphRepository

from app.domains.notifications.application.services import NotificationService
from app.domains.notifications.domain.repository import NotificationRepository
from app.domains.notifications.infrastructure.repository import PostgreSQLNotificationRepository

from app.domains.analytics.application.services import AnalyticsService
from app.domains.analytics.domain.repository import AnalyticsRepository
from app.domains.analytics.infrastructure.repository import PostgreSQLAnalyticsRepository

from app.domains.administration.application.services import AdministrationService
from app.domains.administration.domain.repository import AdministrationRepository
from app.domains.administration.infrastructure.repository import PostgreSQLAdministrationRepository

# ---------- Auth ----------

# The same in-memory instance must be reused between requests.
# Creating a new repository for every request would erase registered users.
_local_auth_repository = InMemoryAuthRepository()
_local_websocket_ticket_store = InMemoryWebSocketTicketStore()
_local_access_token_revocation_store = (
    InMemoryAccessTokenRevocationStore()
)

# HTTPBearer allows Swagger to send an Authorization: Bearer header.
bearer_scheme = HTTPBearer(auto_error=False)


def get_auth_repository() -> AuthRepository:
    """
    Return the current authentication repository.

    Replace this with the PostgreSQL implementation before staging.
    """

    return _local_auth_repository


def get_auth_service() -> AuthService:
    """Construct an authentication service using the active local adapters."""

    return AuthService(
        repository=get_auth_repository(),
        ticket_store=_local_websocket_ticket_store,
        revocation_store=_local_access_token_revocation_store,
    )


async def get_current_access_token_claims(
    credentials: HTTPAuthorizationCredentials | None = Security(
        bearer_scheme
    ),
    service: AuthService = Depends(get_auth_service),
) -> AccessTokenClaims:
    """Validate a bearer token and reject logged-out token identifiers.

    Raises:
        ApiError: If the token is missing, malformed, expired, or revoked.
    """

    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
    ):
        raise ApiError(
            status_code=401,
            code="AUTHENTICATION_REQUIRED",
            message="A valid access token is required.",
        )

    try:
        claims = decode_access_token_claims(
            credentials.credentials
        )
    except AccessTokenExpiredError as exc:
        raise ApiError(
            status_code=401,
            code="TOKEN_EXPIRED",
            message="The access token has expired.",
        ) from exc
    except AccessTokenError as exc:
        raise ApiError(
            status_code=401,
            code="TOKEN_INVALID",
            message="The access token is invalid or expired.",
        ) from exc

    if await service.is_access_token_revoked(claims.token_id):
        raise ApiError(
            status_code=401,
            code="TOKEN_REVOKED",
            message="The access token has been logged out.",
        )

    return claims


async def get_current_user(
    claims: AccessTokenClaims = Depends(
        get_current_access_token_claims
    ),
    service: AuthService = Depends(get_auth_service),
) -> User:
    """Resolve the active user represented by a valid access token.

    Raises:
        ApiError: If the token user is unavailable or the account is inactive.
    """

    user = await service.get_user(claims.subject)

    if user is None:
        raise ApiError(
            status_code=401,
            code="TOKEN_INVALID",
            message="The access token is invalid or expired.",
        )

    if not user.is_active:
        raise ApiError(
            status_code=403,
            code="ACCOUNT_INACTIVE",
            message="This account is inactive.",
        )

    return user


def require_roles(
    *allowed_roles: str,
) -> Callable:
    """
    Create a reusable dependency for role-restricted endpoints.

    Example:
        current_user: User = Depends(require_roles("admin"))
    """

    async def role_dependency(
        current_user: User = Depends(get_current_user),
    ) -> User:
        """Return the user when their role is in the permitted role set."""

        if current_user.role not in allowed_roles:
            raise ApiError(
                status_code=403,
                code="PERMISSION_DENIED",
                message="You do not have permission to perform this action.",
            )

        return current_user

    return role_dependency


# ---------- Users ----------

def get_user_repository() -> UserRepository:
    """Construct the configured user repository."""

    return PostgreSQLUserRepository()


def get_user_service() -> UserService:
    """Construct the user application service."""

    return UserService(get_user_repository())


# ---------- Notes ----------

def get_note_repository() -> NoteRepository:
    """Construct the configured note repository."""

    return PostgreSQLNoteRepository()


def get_note_service() -> NoteService:
    """Construct the note application service."""

    return NoteService(get_note_repository())


# ---------- Study Groups ----------

def get_study_group_repository() -> StudyGroupRepository:
    """Construct the configured study-group repository."""

    return PostgreSQLStudyGroupRepository()


def get_study_group_service() -> StudyGroupService:
    """Construct the study-group application service."""

    return StudyGroupService(get_study_group_repository())


# ---------- Knowledge Graph ----------

def get_knowledge_graph_repository() -> KnowledgeGraphRepository:
    """Construct the configured knowledge-graph repository."""

    return PostgreSQLKnowledgeGraphRepository()


def get_knowledge_graph_service() -> KnowledgeGraphService:
    """Construct the knowledge-graph application service."""

    return KnowledgeGraphService(get_knowledge_graph_repository())


# ---------- Notificatios ----------

def get_notification_repository() -> NotificationRepository:
    """Construct the configured notification repository."""

    return PostgreSQLNotificationRepository()


def get_notification_service() -> NotificationService:
    """Construct the notification application service."""

    return NotificationService(get_notification_repository())


# ---------- Analytics ----------


def get_analytics_repository() -> AnalyticsRepository:
    """Construct the configured analytics repository."""

    return PostgreSQLAnalyticsRepository()


def get_analytics_service() -> AnalyticsService:
    """Construct the analytics application service."""

    return AnalyticsService(get_analytics_repository())


# ---------- Administration ----------


def get_administration_repository() -> AdministrationRepository:
    """Construct the configured administration repository."""

    return PostgreSQLAdministrationRepository()


def get_administration_service() -> AdministrationService:
    """Construct the administration application service."""

    return AdministrationService(get_administration_repository())
