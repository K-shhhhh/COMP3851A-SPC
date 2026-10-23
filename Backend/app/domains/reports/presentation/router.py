"""Authenticated, contextual user-report endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status

from app.api.dependencies import get_current_user, get_report_service
from app.api.error_handlers import ApiError
from app.domains.auth.domain.models import User
from app.domains.reports.application.services import ReportService
from app.domains.reports.domain.exceptions import (
    DuplicateReportError,
    InvalidEvidenceError,
    ReportNotFoundError,
    ReportPermissionDeniedError,
)
from app.domains.reports.domain.models import (
    EvidenceUpload,
    ReportCategory,
    ReportStatus,
    ReportTargetType,
)
from app.domains.reports.presentation.schemas import ReportListResponse, ReportResponse

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.post("", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def create_report(
    target_type: Annotated[ReportTargetType, Form()],
    target_id: Annotated[str, Form(min_length=1, max_length=128)],
    category: Annotated[ReportCategory, Form()],
    description: Annotated[str, Form(min_length=10, max_length=2000)],
    include_limited_context: Annotated[bool, Form()] = False,
    evidence: Annotated[list[UploadFile] | None, File()] = None,
    current_user: User = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
) -> ReportResponse:
    uploads = [
        EvidenceUpload(
            filename=item.filename or "proof-image",
            content_type=item.content_type or "application/octet-stream",
            content=await item.read(),
        )
        for item in (evidence or [])
    ]
    try:
        report = await service.create_report(
            reporter_user_id=current_user.id,
            target_type=target_type,
            target_id=target_id,
            category=category,
            description=description,
            include_limited_context=include_limited_context,
            evidence=uploads,
        )
    except InvalidEvidenceError as exc:
        raise ApiError(status_code=422, code="INVALID_REPORT_EVIDENCE", message=str(exc)) from exc
    except ReportPermissionDeniedError as exc:
        raise ApiError(status_code=403, code="REPORT_PERMISSION_DENIED", message=str(exc)) from exc
    except ReportNotFoundError as exc:
        raise ApiError(status_code=404, code="REPORT_TARGET_NOT_FOUND", message=str(exc)) from exc
    except DuplicateReportError as exc:
        raise ApiError(status_code=409, code="DUPLICATE_REPORT", message=str(exc)) from exc
    except ValueError as exc:
        raise ApiError(status_code=422, code="INVALID_REPORT", message=str(exc)) from exc
    return ReportResponse.model_validate(report)


@router.get("", response_model=ReportListResponse)
async def list_my_reports(
    report_status: ReportStatus | None = Query(default=None, alias="status"),
    cursor: str | None = Query(default=None, max_length=256),
    limit: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
) -> ReportListResponse:
    page = await service.list_reports(
        reporter_user_id=current_user.id,
        status=report_status,
        cursor=cursor,
        limit=limit,
    )
    return ReportListResponse(
        items=[ReportResponse.model_validate(item) for item in page.items],
        next_cursor=page.next_cursor,
    )


@router.get("/{report_id}", response_model=ReportResponse)
async def get_my_report(
    report_id: str,
    current_user: User = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
) -> ReportResponse:
    try:
        report = await service.get_report(
            reporter_user_id=current_user.id,
            report_id=report_id,
        )
    except ReportNotFoundError as exc:
        raise ApiError(status_code=404, code="REPORT_NOT_FOUND", message=str(exc)) from exc
    return ReportResponse.model_validate(report)
