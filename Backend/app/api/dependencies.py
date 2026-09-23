"""Construct application services and enforce request authentication.

This module is the backend composition boundary. It currently injects local
in-memory authentication stores; staging must select PostgreSQL and Redis
implementations when those integrations are ready.
"""
import os
from collections.abc import Callable

from redis.asyncio import Redis

from fastapi import Depends, Security
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from app.api.error_handlers import ApiError
from app.core.config import settings
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
from app.domains.auth.infrastructure.redis_auth_repository import (
    RedisAuthRepository,
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
from app.domains.notes.domain.processing import (
    AttachmentProcessingDispatcher,
)
from app.domains.notes.domain.repository import AttachmentRepository
from app.domains.notes.domain.storage import AttachmentStorage
from app.domains.notes.infrastructure.local_storage import (
    LocalAttachmentStorage,
)
from app.domains.notes.infrastructure.celery_processing import (
    CeleryAttachmentProcessingDispatcher,
)
from app.domains.notes.infrastructure.memory_repository import (
    InMemoryAttachmentRepository,
)
from app.domains.notes.infrastructure.redis_repository import (
    RedisAttachmentRepository,
)

from app.domains.chats.application.services import ChatService
from app.domains.chats.domain.answering import ChatAnswerGenerator
from app.domains.chats.domain.repository import ChatRepository
from app.domains.chats.domain.retrieval import ReadyNoteChunkRepository
from app.domains.chats.infrastructure.memory_answering import (
    LocalGroundedAnswerGenerator,
)
from app.domains.chats.infrastructure.memory_repository import (
    InMemoryChatRepository,
)
from app.domains.chats.infrastructure.redis_chat_repository import (
    RedisChatRepository,
)
from app.domains.chats.infrastructure.memory_retrieval import (
    InMemoryReadyNoteChunkRepository,
)
from app.domains.chats.infrastructure.redis_retrieval import (
    RedisReadyNoteChunkRepository,
)

# ---------- Real integration switch template ----------
#
# Keep these imports commented while the PostgreSQL and RAG adapters are only
# placeholders. Uncomment them after the database developer and Krish have
# implemented the constructors and their integration tests pass.
#
# from app.core.database import async_session_factory
# from app.domains.auth.infrastructure.repository import (
#     PostgreSQLAuthRepository,
# )
# from app.domains.notes.infrastructure.repository import (
#     PostgreSQLAttachmentRepository,
# )
# from app.domains.chats.infrastructure.repository import (
#     PostgreSQLChatRepository,
# )
# from app.domains.chats.infrastructure.retrieval import (
#     PostgreSQLReadyNoteChunkRepository,
# )
# from app.domains.chats.infrastructure.rag_answering import (
#     KrishRagAnswerGenerator,
# )

from app.domains.chats.infrastructure.rag_answering import (
    KrishRagAnswerGenerator,
)

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

# ---------- Shared Redis client ----------

# One shared client, reused across auth, notes, and chats -- Celery tasks
# run in a separate container and cannot see this process's in-memory
# state, so anything that needs to survive a restart or be visible to the
# worker lives in Redis instead. Interim until PostgreSQL/pgvector adapters
# replace these piece by piece.
_redis_client = Redis.from_url(
    os.environ.get("REDIS_URL", "redis://redis:6379/0"),
    decode_responses=True,
)

# ---------- Auth ----------

# Redis-backed so registered accounts survive a backend restart, instead of
# disappearing the moment the process restarts.
_local_auth_repository = RedisAuthRepository(_redis_client)
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

    # REAL DATABASE SWITCH:
    # return PostgreSQLAuthRepository(
    #     session_factory=async_session_factory,
    # )
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

# Attachment and chunk repositories reuse the shared _redis_client defined
# above with auth, for the same reason -- the worker process needs to reach
# the same data, until Kaung's PostgreSQL adapter is ready.
_local_attachment_repository = RedisAttachmentRepository(_redis_client)

# Shared retrieval is declared here because the Celery worker writes chunks
# that the personal Chat service later reads, from a separate process.
_local_ready_note_chunk_repository = RedisReadyNoteChunkRepository(_redis_client)

_local_attachment_storage: AttachmentStorage | None = None
_local_attachment_processing_dispatcher = (
    CeleryAttachmentProcessingDispatcher()
)


def get_attachment_repository() -> AttachmentRepository:
    """Return the Redis-backed attachment repository, shared across the
    backend and worker processes for Celery background processing.

    Interim step until Kaung's PostgreSQL adapter is ready -- see
    redis_repository.py's module docstring for why this exists.
    """

    # REAL DATABASE SWITCH:
    # return PostgreSQLAttachmentRepository(
    #     session_factory=async_session_factory,
    # )
    return _local_attachment_repository


def get_attachment_storage() -> AttachmentStorage:
    """Lazily initialize and return private PDF storage.

    Delaying directory creation keeps imports side-effect free and lets tests
    replace the storage dependency before touching the real local directory.
    """

    global _local_attachment_storage

    if _local_attachment_storage is None:
        _local_attachment_storage = LocalAttachmentStorage(
            settings.NOTE_STORAGE_DIRECTORY
        )

    return _local_attachment_storage


def get_attachment_processing_dispatcher(
) -> AttachmentProcessingDispatcher:
    """Return Krish's real processing dispatcher (extraction, chunking,
    embedding, safety-checking, captioning -- the full pipeline)."""

    return _local_attachment_processing_dispatcher


def get_note_service() -> NoteService:
    """Construct Notes use cases from the active adapters."""

    return NoteService(
        repository=get_attachment_repository(),
        storage=get_attachment_storage(),
        processing_dispatcher=get_attachment_processing_dispatcher(),
        maximum_file_size_bytes=settings.MAX_NOTE_UPLOAD_SIZE_BYTES,
    )


# ---------- Personal Chat ----------

# Redis-backed so conversations and their message history survive a
# backend restart, reusing the shared _redis_client defined with auth.
_local_chat_repository = RedisChatRepository(_redis_client)
_local_chat_answer_generator = LocalGroundedAnswerGenerator()


def get_chat_repository() -> ChatRepository:
    """Return temporary local personal-chat persistence."""

    # REAL DATABASE SWITCH:
    # return PostgreSQLChatRepository(
    #     session_factory=async_session_factory,
    # )
    return _local_chat_repository


def get_ready_note_chunk_repository() -> ReadyNoteChunkRepository:
    """Return temporary authorized-chunk storage for contract testing."""

    # REAL DATABASE/PGVECTOR SWITCH:
    # return PostgreSQLReadyNoteChunkRepository(
    #     session_factory=async_session_factory,
    # )
    return _local_ready_note_chunk_repository


def get_chat_answer_generator() -> ChatAnswerGenerator:
    """Return Krish's real RAG answer generator."""

    return KrishRagAnswerGenerator()


def get_chat_service() -> ChatService:
    """Construct personal-chat use cases from the active adapters."""

    return ChatService(
        repository=get_chat_repository(),
        chunk_repository=get_ready_note_chunk_repository(),
        answer_generator=get_chat_answer_generator(),
        maximum_question_length=settings.MAX_CHAT_QUESTION_LENGTH,
    )


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
