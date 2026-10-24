"""Validated public schemas for the administration API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domains.administration.domain.models import (
    AdministrationAttachmentSource,
    AdministrationAttachmentStatus,
    AdministrationGroupStatus,
    AdministrationGroupVisibility,
    AdministrationHealth,
    AdministrationLogSeverity,
    AdministrationUserRole,
    AdministrationUserStatus,
    AdminReportActivityType,
    AdminReportGovernanceAction,
    AdminReportResolutionOutcome,
)
from app.domains.reports.domain.models import (
    ReportCategory,
    ReportStatus,
    ReportTargetType,
)


class DomainResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AdminMeResponse(DomainResponse):
    user_id: str
    full_name: str
    email: str
    role: str
    status: str


class GovernanceActionRequest(BaseModel):
    reason: str = Field(min_length=10, max_length=1000)


class GovernanceActionResponse(DomainResponse):
    resource_id: str
    status: str
    changed_at: datetime


class SystemStatusResponse(DomainResponse):
    application_name: str
    version: str
    environment: str
    overall_status: AdministrationHealth
    database_status: AdministrationHealth
    worker_status: AdministrationHealth


class ProcessingFailureResponse(DomainResponse):
    attachment_id: int
    title: str
    file_name: str
    uploader_name: str
    safe_error: str
    occurred_at: datetime


class SystemLogResponse(DomainResponse):
    event_id: str
    occurred_at: datetime
    severity: AdministrationLogSeverity
    service: str
    message: str
    request_id: str | None


class DashboardResponse(DomainResponse):
    active_users: int
    active_study_groups: int
    stored_notes: int
    processing_failures_24h: int
    open_reports: int
    under_review_reports: int
    recently_submitted_reports: int
    recent_processing_failures: tuple[ProcessingFailureResponse, ...]
    recent_system_events: tuple[SystemLogResponse, ...]
    recent_reports: tuple["AdminReportSummaryResponse", ...]


class AdminUserSummaryResponse(DomainResponse):
    user_id: str
    full_name: str
    email: str
    role: AdministrationUserRole
    status: AdministrationUserStatus
    created_at: datetime
    last_active_at: datetime | None


class AdminUserDetailsResponse(DomainResponse):
    user: AdminUserSummaryResponse
    notes_count: int
    groups_joined_count: int
    groups_owned_count: int


class AdminUserPageResponse(DomainResponse):
    items: tuple[AdminUserSummaryResponse, ...]
    next_cursor: str | None


class AdminGroupSummaryResponse(DomainResponse):
    group_id: str
    name: str
    visibility: AdministrationGroupVisibility
    owner_name: str
    member_count: int
    channel_count: int
    status: AdministrationGroupStatus
    created_at: datetime


class AdminGroupChannelResponse(DomainResponse):
    channel_id: str
    name: str


class AdminGroupDetailsResponse(DomainResponse):
    group: AdminGroupSummaryResponse
    description: str | None
    current_owner_id: str
    created_by_id: str
    created_by_name: str
    owner_count: int
    admin_count: int
    ordinary_member_count: int
    channels: tuple[AdminGroupChannelResponse, ...]


class AdminGroupPageResponse(DomainResponse):
    items: tuple[AdminGroupSummaryResponse, ...]
    next_cursor: str | None


class AdminAttachmentSummaryResponse(DomainResponse):
    attachment_id: int
    title: str
    file_name: str
    uploader_name: str
    source: AdministrationAttachmentSource
    file_size_bytes: int
    status: AdministrationAttachmentStatus
    uploaded_at: datetime
    removed: bool


class AdminAttachmentDetailsResponse(DomainResponse):
    attachment: AdminAttachmentSummaryResponse
    uploader_user_id: str
    content_type: str
    processing_progress: int
    processing_started_at: datetime | None
    processing_completed_at: datetime | None
    processing_duration_seconds: int | None
    safe_processing_error: str | None


class AdminAttachmentPageResponse(DomainResponse):
    items: tuple[AdminAttachmentSummaryResponse, ...]
    next_cursor: str | None


class SystemLogPageResponse(DomainResponse):
    items: tuple[SystemLogResponse, ...]
    next_cursor: str | None


class AdminReportSummaryResponse(DomainResponse):
    report_id: str
    created_at: datetime
    category: ReportCategory
    target_type: ReportTargetType
    target_description: str
    status: ReportStatus


class AdminReportEvidenceResponse(DomainResponse):
    evidence_id: str
    filename: str
    content_type: str


class AdminReportActivityResponse(DomainResponse):
    activity_id: str
    event_type: AdminReportActivityType
    summary: str
    administrator_user_id: str | None
    administrator_name: str | None
    occurred_at: datetime


class AdminReportDetailsResponse(DomainResponse):
    report: AdminReportSummaryResponse
    reporter_user_id: str
    reporter_name: str
    description: str
    target_snapshot: dict[str, object]
    limited_context_snapshot: tuple[dict[str, object], ...]
    evidence: tuple[AdminReportEvidenceResponse, ...]
    activity: tuple[AdminReportActivityResponse, ...]
    resolved_at: datetime | None
    resolution_outcome: AdminReportResolutionOutcome | None
    internal_resolution_reason: str | None
    public_summary: str | None


class AdminReportPageResponse(DomainResponse):
    items: tuple[AdminReportSummaryResponse, ...]
    next_cursor: str | None


class AdminReportNoteRequest(BaseModel):
    note: str = Field(min_length=2, max_length=2000)


class AdminReportResolutionRequest(BaseModel):
    outcome: AdminReportResolutionOutcome
    reason: str = Field(min_length=10, max_length=2000)
    public_summary: str = Field(min_length=10, max_length=1000)


class AdminReportDismissRequest(BaseModel):
    reason: str = Field(min_length=10, max_length=2000)
    public_summary: str = Field(min_length=10, max_length=1000)


class AdminReportGovernanceRequest(BaseModel):
    action: AdminReportGovernanceAction
    reason: str = Field(min_length=10, max_length=1000)
