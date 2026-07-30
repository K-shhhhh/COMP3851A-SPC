from app.domains.auth.application.services import AuthService
from app.domains.auth.domain.repository import AuthRepository
from app.domains.auth.infrastructure.repository import PostgreSQLAuthRepository

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

def get_auth_repository() -> AuthRepository:
    return PostgreSQLAuthRepository()


def get_auth_service() -> AuthService:
    return AuthService(get_auth_repository())


# ---------- Users ----------

def get_user_repository() -> UserRepository:
    return PostgreSQLUserRepository()


def get_user_service() -> UserService:
    return UserService(get_user_repository())


# ---------- Notes ----------

def get_note_repository() -> NoteRepository:
    return PostgreSQLNoteRepository()


def get_note_service() -> NoteService:
    return NoteService(get_note_repository())


# ---------- Study Groups ----------

def get_study_group_repository() -> StudyGroupRepository:
    return PostgreSQLStudyGroupRepository()


def get_study_group_service() -> StudyGroupService:
    return StudyGroupService(get_study_group_repository())


# ---------- Knowledge Graph ----------

def get_knowledge_graph_repository() -> KnowledgeGraphRepository:
    return PostgreSQLKnowledgeGraphRepository()


def get_knowledge_graph_service() -> KnowledgeGraphService:
    return KnowledgeGraphService(get_knowledge_graph_repository())


# ---------- Notificatios ----------

def get_notification_repository() -> NotificationRepository:
    return PostgreSQLNotificationRepository()


def get_notification_service() -> NotificationService:
    return NotificationService(get_notification_repository())


# ---------- Analytics ----------


def get_analytics_repository() -> AnalyticsRepository:
    return PostgreSQLAnalyticsRepository()


def get_analytics_service() -> AnalyticsService:
    return AnalyticsService(get_analytics_repository())


# ---------- Administration ----------


def get_administration_repository() -> AdministrationRepository:
    return PostgreSQLAdministrationRepository()


def get_administration_service() -> AdministrationService:
    return AdministrationService(get_administration_repository())