"""Framework-independent administration domain models.

These models intentionally contain no SQLAlchemy or FastAPI code. They define
the backend contract that the PostgreSQL adapter and admin frontend integrate
against. Report review reuses the canonical report enums while exposing only
the evidence and limited context preserved for the submitted report.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.domains.reports.domain.models import (
    ReportCategory,
    ReportStatus,
    ReportTargetType,
)


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


class AdminReportResolutionOutcome(StrEnum):
    NO_VIOLATION = "no_violation"
    CONTENT_REMOVED = "content_removed"
    USER_DEACTIVATED = "user_deactivated"
    GROUP_REMOVED = "group_removed"
    FILE_REMOVED = "file_removed"
    DUPLICATE = "duplicate"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class AdminReportGovernanceAction(StrEnum):
    REMOVE_MESSAGE = "remove_message"
    DEACTIVATE_MESSAGE_AUTHOR = "deactivate_message_author"
    REMOVE_GROUP = "remove_group"
    REMOVE_FILE = "remove_file"


class AdminReportActivityType(StrEnum):
    REPORT_SUBMITTED = "report_submitted"
    REVIEW_STARTED = "review_started"
    NOTE_ADDED = "note_added"
    EVIDENCE_VIEWED = "evidence_viewed"
    GOVERNANCE_ACTION = "governance_action"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


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
class AdminReportSummary:
    report_id: str
    created_at: datetime
    category: ReportCategory
    target_type: ReportTargetType
    target_description: str
    status: ReportStatus


@dataclass(frozen=True, slots=True)
class AdminReportEvidence:
    evidence_id: str
    filename: str
    content_type: str


@dataclass(frozen=True, slots=True)
class AdminReportActivity:
    activity_id: str
    event_type: AdminReportActivityType
    summary: str
    administrator_user_id: str | None
    administrator_name: str | None
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class AdminReportDetails:
    report: AdminReportSummary
    reporter_user_id: str
    reporter_name: str
    description: str
    target_snapshot: dict[str, object]
    limited_context_snapshot: tuple[dict[str, object], ...]
    evidence: tuple[AdminReportEvidence, ...]
    activity: tuple[AdminReportActivity, ...]
    resolved_at: datetime | None
    resolution_outcome: AdminReportResolutionOutcome | None
    internal_resolution_reason: str | None
    public_summary: str | None


@dataclass(frozen=True, slots=True)
class AdminReportPage:
    items: tuple[AdminReportSummary, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class AdminEvidenceFile:
    evidence_id: str
    filename: str
    content_type: str
    content: bytes


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    active_users: int
    active_study_groups: int
    stored_notes: int
    processing_failures_24h: int
    open_reports: int
    under_review_reports: int
    recently_submitted_reports: int
    recent_processing_failures: tuple[ProcessingFailure, ...]
    recent_system_events: tuple[SystemLogEntry, ...]
    recent_reports: tuple[AdminReportSummary, ...]


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
