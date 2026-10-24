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
    recent_processing_failures: tuple[ProcessingFailureResponse, ...]
    recent_system_events: tuple[SystemLogResponse, ...]


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
