"""Framework-independent administration domain models.

These models intentionally contain no SQLAlchemy or FastAPI code. They define
the backend contract that the PostgreSQL adapter and admin frontend integrate
against. Report-review models live in the reports domain and are deliberately
out of scope here.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class AdministrationHealth(StrEnum):
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class AdministrationUserRole(StrEnum):
    STUDENT = "student"
    ADMIN = "admin"


class AdministrationUserStatus(StrEnum):
    ACTIVE = "active"
    DEACTIVATED = "deactivated"


class AdministrationGroupVisibility(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"


class AdministrationGroupStatus(StrEnum):
    ACTIVE = "active"
    REMOVED = "removed"


class AdministrationAttachmentStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class AdministrationAttachmentSource(StrEnum):
    MY_NOTES = "my_notes"
    PERSONAL_CHAT = "personal_chat"
    STUDY_GROUP = "study_group"


class AdministrationLogSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class AdministrationActor:
    """Administrator performing a governance action."""

    user_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class SystemStatus:
    application_name: str
    version: str
    environment: str
    overall_status: AdministrationHealth
    database_status: AdministrationHealth
    worker_status: AdministrationHealth


@dataclass(frozen=True, slots=True)
class ProcessingFailure:
    attachment_id: int
    title: str
    file_name: str
    uploader_name: str
    safe_error: str
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class SystemLogEntry:
    event_id: str
    occurred_at: datetime
    severity: AdministrationLogSeverity
    service: str
    message: str
    request_id: str | None


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    active_users: int
    active_study_groups: int
    stored_notes: int
    processing_failures_24h: int
    recent_processing_failures: tuple[ProcessingFailure, ...]
    recent_system_events: tuple[SystemLogEntry, ...]


@dataclass(frozen=True, slots=True)
class AdminUserSummary:
    user_id: str
    full_name: str
    email: str
    role: AdministrationUserRole
    status: AdministrationUserStatus
    created_at: datetime
    last_active_at: datetime | None


@dataclass(frozen=True, slots=True)
class AdminUserDetails:
    user: AdminUserSummary
    notes_count: int
    groups_joined_count: int
    groups_owned_count: int


@dataclass(frozen=True, slots=True)
class AdminUserPage:
    items: tuple[AdminUserSummary, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class AdminGroupSummary:
    group_id: str
    name: str
    visibility: AdministrationGroupVisibility
    owner_name: str
    member_count: int
    channel_count: int
    status: AdministrationGroupStatus
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AdminGroupChannel:
    channel_id: str
    name: str


@dataclass(frozen=True, slots=True)
class AdminGroupDetails:
    group: AdminGroupSummary
    description: str | None
    current_owner_id: str
    created_by_id: str
    created_by_name: str
    owner_count: int
    admin_count: int
    ordinary_member_count: int
    channels: tuple[AdminGroupChannel, ...]


@dataclass(frozen=True, slots=True)
class AdminGroupPage:
    items: tuple[AdminGroupSummary, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class AdminAttachmentSummary:
    attachment_id: int
    title: str
    file_name: str
    uploader_name: str
    source: AdministrationAttachmentSource
    file_size_bytes: int
    status: AdministrationAttachmentStatus
    uploaded_at: datetime
    removed: bool


@dataclass(frozen=True, slots=True)
class AdminAttachmentDetails:
    attachment: AdminAttachmentSummary
    uploader_user_id: str
    content_type: str
    processing_progress: int
    processing_started_at: datetime | None
    processing_completed_at: datetime | None
    processing_duration_seconds: int | None
    safe_processing_error: str | None


@dataclass(frozen=True, slots=True)
class AdminAttachmentPage:
    items: tuple[AdminAttachmentSummary, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class SystemLogPage:
    items: tuple[SystemLogEntry, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class GovernanceActionResult:
    resource_id: str
    status: str
    changed_at: datetime
