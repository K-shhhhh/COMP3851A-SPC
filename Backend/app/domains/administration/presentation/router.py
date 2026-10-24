"""Admin-only HTTP boundary for governance and operational visibility."""

from contextlib import contextmanager
from datetime import datetime
from io import BytesIO
from typing import Iterator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_administration_service, require_roles
from app.api.error_handlers import ApiError
from app.domains.administration.application.services import AdministrationService
from app.domains.administration.domain.exceptions import (
    AdministrationConflictError,
    AdministrationResourceNotFoundError,
    AdministrationValidationError,
)
from app.domains.administration.domain.models import (
    AdministrationAttachmentSource,
    AdministrationAttachmentStatus,
    AdministrationGroupStatus,
    AdministrationGroupVisibility,
    AdministrationLogSeverity,
    AdministrationUserRole,
    AdministrationUserStatus,
)
from app.domains.administration.presentation.schemas import (
    AdminAttachmentDetailsResponse,
    AdminAttachmentPageResponse,
    AdminGroupDetailsResponse,
    AdminGroupPageResponse,
    AdminMeResponse,
    AdminUserDetailsResponse,
    AdminUserPageResponse,
    AdminReportDetailsResponse,
    AdminReportDismissRequest,
    AdminReportGovernanceRequest,
    AdminReportNoteRequest,
    AdminReportPageResponse,
    AdminReportResolutionRequest,
    DashboardResponse,
    GovernanceActionRequest,
    GovernanceActionResponse,
    SystemLogPageResponse,
    SystemLogResponse,
    SystemStatusResponse,
)
from app.domains.auth.domain.models import User
from app.domains.reports.domain.models import ReportStatus, ReportTargetType


ADMIN_REQUIRED = require_roles("admin")


router = APIRouter(
    prefix="/administration",
    tags=["Administration"],
    dependencies=[Depends(ADMIN_REQUIRED)],
)


@contextmanager
def administration_errors() -> Iterator[None]:
    """Map domain-safe errors into the shared API error envelope."""

    try:
        yield
    except AdministrationResourceNotFoundError as exc:
        raise ApiError(status_code=404, code="ADMIN_RESOURCE_NOT_FOUND", message=str(exc)) from exc
    except AdministrationConflictError as exc:
        raise ApiError(status_code=409, code="ADMIN_ACTION_CONFLICT", message=str(exc)) from exc
    except AdministrationValidationError as exc:
        raise ApiError(status_code=422, code="ADMIN_ACTION_INVALID", message=str(exc)) from exc


@router.get("/me", response_model=AdminMeResponse)
async def get_admin_identity(
    current_admin: User = Depends(ADMIN_REQUIRED),
) -> AdminMeResponse:
    return AdminMeResponse(
        user_id=current_admin.id,
        full_name=current_admin.full_name,
        email=current_admin.email,
        role=current_admin.role,
        status="active",
    )


@router.get("/system-status", response_model=SystemStatusResponse)
async def get_system_status(
    service: AdministrationService = Depends(get_administration_service),
) -> SystemStatusResponse:
    return SystemStatusResponse.model_validate(await service.get_system_status())


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    service: AdministrationService = Depends(get_administration_service),
) -> DashboardResponse:
    return DashboardResponse.model_validate(await service.get_dashboard())


@router.get("/users", response_model=AdminUserPageResponse)
async def list_users(
    search: str | None = Query(default=None, max_length=200),
    status: AdministrationUserStatus | None = None,
    role: AdministrationUserRole | None = None,
    cursor: str | None = Query(default=None, max_length=500),
    limit: int = Query(default=25, ge=1, le=100),
    service: AdministrationService = Depends(get_administration_service),
) -> AdminUserPageResponse:
    page = await service.list_users(
        search=search,
        status=status,
        role=role,
        cursor=cursor,
        limit=limit,
    )
    return AdminUserPageResponse.model_validate(page)


@router.get("/users/{user_id}", response_model=AdminUserDetailsResponse)
async def get_user(
    user_id: str,
    service: AdministrationService = Depends(get_administration_service),
) -> AdminUserDetailsResponse:
    with administration_errors():
        return AdminUserDetailsResponse.model_validate(await service.get_user(user_id))


@router.post("/users/{user_id}/deactivate", response_model=GovernanceActionResponse)
async def deactivate_user(
    user_id: str,
    request: GovernanceActionRequest,
    current_admin: User = Depends(ADMIN_REQUIRED),
    service: AdministrationService = Depends(get_administration_service),
) -> GovernanceActionResponse:
    with administration_errors():
        result = await service.deactivate_user(
            current_admin_id=current_admin.id,
            target_user_id=user_id,
            reason=request.reason,
        )
        return GovernanceActionResponse.model_validate(result)


@router.post("/users/{user_id}/reactivate", response_model=GovernanceActionResponse)
async def reactivate_user(
    user_id: str,
    request: GovernanceActionRequest,
    current_admin: User = Depends(ADMIN_REQUIRED),
    service: AdministrationService = Depends(get_administration_service),
) -> GovernanceActionResponse:
    with administration_errors():
        result = await service.reactivate_user(
            current_admin_id=current_admin.id,
            target_user_id=user_id,
            reason=request.reason,
        )
        return GovernanceActionResponse.model_validate(result)


@router.get("/study-groups", response_model=AdminGroupPageResponse)
async def list_groups(
    search: str | None = Query(default=None, max_length=200),
    visibility: AdministrationGroupVisibility | None = None,
    status: AdministrationGroupStatus | None = None,
    cursor: str | None = Query(default=None, max_length=500),
    limit: int = Query(default=25, ge=1, le=100),
    service: AdministrationService = Depends(get_administration_service),
) -> AdminGroupPageResponse:
    page = await service.list_groups(
        search=search,
        visibility=visibility,
        status=status,
        cursor=cursor,
        limit=limit,
    )
    return AdminGroupPageResponse.model_validate(page)


@router.get("/study-groups/{group_id}", response_model=AdminGroupDetailsResponse)
async def get_group(
    group_id: str,
    service: AdministrationService = Depends(get_administration_service),
) -> AdminGroupDetailsResponse:
    with administration_errors():
        return AdminGroupDetailsResponse.model_validate(await service.get_group(group_id))


@router.post("/study-groups/{group_id}/remove", response_model=GovernanceActionResponse)
async def remove_group(
    group_id: str,
    request: GovernanceActionRequest,
    current_admin: User = Depends(ADMIN_REQUIRED),
    service: AdministrationService = Depends(get_administration_service),
) -> GovernanceActionResponse:
    with administration_errors():
        result = await service.remove_group(
            current_admin_id=current_admin.id,
            group_id=group_id,
            reason=request.reason,
        )
        return GovernanceActionResponse.model_validate(result)


@router.post("/study-groups/{group_id}/restore", response_model=GovernanceActionResponse)
async def restore_group(
    group_id: str,
    request: GovernanceActionRequest,
    current_admin: User = Depends(ADMIN_REQUIRED),
    service: AdministrationService = Depends(get_administration_service),
) -> GovernanceActionResponse:
    with administration_errors():
        result = await service.restore_group(
            current_admin_id=current_admin.id,
            group_id=group_id,
            reason=request.reason,
        )
        return GovernanceActionResponse.model_validate(result)


@router.get("/attachments", response_model=AdminAttachmentPageResponse)
async def list_attachments(
    search: str | None = Query(default=None, max_length=200),
    status: AdministrationAttachmentStatus | None = None,
    source: AdministrationAttachmentSource | None = None,
    include_removed: bool = False,
    cursor: str | None = Query(default=None, max_length=500),
    limit: int = Query(default=25, ge=1, le=100),
    service: AdministrationService = Depends(get_administration_service),
) -> AdminAttachmentPageResponse:
    page = await service.list_attachments(
        search=search,
        status=status,
        source=source,
        include_removed=include_removed,
        cursor=cursor,
        limit=limit,
    )
    return AdminAttachmentPageResponse.model_validate(page)


@router.get("/attachments/{attachment_id}", response_model=AdminAttachmentDetailsResponse)
async def get_attachment(
    attachment_id: int,
    service: AdministrationService = Depends(get_administration_service),
) -> AdminAttachmentDetailsResponse:
    with administration_errors():
        return AdminAttachmentDetailsResponse.model_validate(
            await service.get_attachment(attachment_id)
        )


@router.delete("/attachments/{attachment_id}", response_model=GovernanceActionResponse)
async def remove_attachment(
    attachment_id: int,
    request: GovernanceActionRequest,
    current_admin: User = Depends(ADMIN_REQUIRED),
    service: AdministrationService = Depends(get_administration_service),
) -> GovernanceActionResponse:
    with administration_errors():
        result = await service.remove_attachment(
            current_admin_id=current_admin.id,
            attachment_id=attachment_id,
            reason=request.reason,
        )
        return GovernanceActionResponse.model_validate(result)


@router.post("/attachments/{attachment_id}/retry", response_model=GovernanceActionResponse)
async def retry_attachment(
    attachment_id: int,
    request: GovernanceActionRequest,
    current_admin: User = Depends(ADMIN_REQUIRED),
    service: AdministrationService = Depends(get_administration_service),
) -> GovernanceActionResponse:
    with administration_errors():
        result = await service.retry_attachment(
            current_admin_id=current_admin.id,
            attachment_id=attachment_id,
            reason=request.reason,
        )
        return GovernanceActionResponse.model_validate(result)


@router.get("/system-logs", response_model=SystemLogPageResponse)
async def list_system_logs(
    severity: AdministrationLogSeverity | None = None,
    service_name: str | None = Query(default=None, alias="service", max_length=100),
    request_id: str | None = Query(default=None, max_length=200),
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    cursor: str | None = Query(default=None, max_length=500),
    limit: int = Query(default=25, ge=1, le=100),
    administration_service: AdministrationService = Depends(get_administration_service),
) -> SystemLogPageResponse:
    with administration_errors():
        page = await administration_service.list_system_logs(
            severity=severity,
            service=service_name,
            request_id=request_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            cursor=cursor,
            limit=limit,
        )
        return SystemLogPageResponse.model_validate(page)


@router.get("/system-logs/{event_id}", response_model=SystemLogResponse)
async def get_system_log(
    event_id: str,
    service: AdministrationService = Depends(get_administration_service),
) -> SystemLogResponse:
    with administration_errors():
        return SystemLogResponse.model_validate(await service.get_system_log(event_id))


@router.get("/reports", response_model=AdminReportPageResponse)
async def list_reports(
    search: str | None = Query(default=None, max_length=200),
    status: ReportStatus | None = None,
    target_type: ReportTargetType | None = None,
    cursor: str | None = Query(default=None, max_length=500),
    limit: int = Query(default=25, ge=1, le=100),
    service: AdministrationService = Depends(get_administration_service),
) -> AdminReportPageResponse:
    page = await service.list_reports(
        search=search,
        status=status,
        target_type=target_type,
        cursor=cursor,
        limit=limit,
    )
    return AdminReportPageResponse.model_validate(page)


@router.get("/reports/{report_id}", response_model=AdminReportDetailsResponse)
async def get_report(
    report_id: str,
    service: AdministrationService = Depends(get_administration_service),
) -> AdminReportDetailsResponse:
    with administration_errors():
        return AdminReportDetailsResponse.model_validate(
            await service.get_report(report_id)
        )


@router.post(
    "/reports/{report_id}/start-review",
    response_model=AdminReportDetailsResponse,
)
async def start_report_review(
    report_id: str,
    request: GovernanceActionRequest,
    current_admin: User = Depends(ADMIN_REQUIRED),
    service: AdministrationService = Depends(get_administration_service),
) -> AdminReportDetailsResponse:
    with administration_errors():
        return AdminReportDetailsResponse.model_validate(
            await service.start_report_review(
                current_admin_id=current_admin.id,
                report_id=report_id,
                reason=request.reason,
            )
        )


@router.post("/reports/{report_id}/notes", response_model=AdminReportDetailsResponse)
async def add_report_note(
    report_id: str,
    request: AdminReportNoteRequest,
    current_admin: User = Depends(ADMIN_REQUIRED),
    service: AdministrationService = Depends(get_administration_service),
) -> AdminReportDetailsResponse:
    with administration_errors():
        return AdminReportDetailsResponse.model_validate(
            await service.add_report_note(
                current_admin_id=current_admin.id,
                report_id=report_id,
                note=request.note,
            )
        )


@router.post("/reports/{report_id}/resolve", response_model=AdminReportDetailsResponse)
async def resolve_report(
    report_id: str,
    request: AdminReportResolutionRequest,
    current_admin: User = Depends(ADMIN_REQUIRED),
    service: AdministrationService = Depends(get_administration_service),
) -> AdminReportDetailsResponse:
    with administration_errors():
        return AdminReportDetailsResponse.model_validate(
            await service.resolve_report(
                current_admin_id=current_admin.id,
                report_id=report_id,
                outcome=request.outcome,
                reason=request.reason,
                public_summary=request.public_summary,
            )
        )


@router.post("/reports/{report_id}/dismiss", response_model=AdminReportDetailsResponse)
async def dismiss_report(
    report_id: str,
    request: AdminReportDismissRequest,
    current_admin: User = Depends(ADMIN_REQUIRED),
    service: AdministrationService = Depends(get_administration_service),
) -> AdminReportDetailsResponse:
    with administration_errors():
        return AdminReportDetailsResponse.model_validate(
            await service.dismiss_report(
                current_admin_id=current_admin.id,
                report_id=report_id,
                reason=request.reason,
                public_summary=request.public_summary,
            )
        )


@router.post("/reports/{report_id}/actions", response_model=GovernanceActionResponse)
async def perform_report_governance_action(
    report_id: str,
    request: AdminReportGovernanceRequest,
    current_admin: User = Depends(ADMIN_REQUIRED),
    service: AdministrationService = Depends(get_administration_service),
) -> GovernanceActionResponse:
    with administration_errors():
        return GovernanceActionResponse.model_validate(
            await service.perform_report_governance_action(
                current_admin_id=current_admin.id,
                report_id=report_id,
                action=request.action,
                reason=request.reason,
            )
        )


@router.get("/reports/{report_id}/evidence/{evidence_id}")
async def get_report_evidence(
    report_id: str,
    evidence_id: str,
    current_admin: User = Depends(ADMIN_REQUIRED),
    service: AdministrationService = Depends(get_administration_service),
) -> StreamingResponse:
    with administration_errors():
        evidence = await service.get_report_evidence(
            current_admin_id=current_admin.id,
            report_id=report_id,
            evidence_id=evidence_id,
        )
        safe_name = (
            evidence.filename.replace('"', "").replace("\r", "").replace("\n", "")
        )
        return StreamingResponse(
            BytesIO(evidence.content),
            media_type=evidence.content_type,
            headers={
                "Content-Disposition": f'inline; filename="{safe_name}"',
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )
