"""Report request and response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domains.reports.domain.models import ReportCategory, ReportStatus, ReportTargetType


class ReportEvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    evidence_id: str
    filename: str
    content_type: str


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    report_id: str
    target_type: ReportTargetType
    target_id: str
    category: ReportCategory
    description: str
    status: ReportStatus
    target_snapshot: dict[str, object]
    limited_context_snapshot: list[dict[str, object]]
    evidence: list[ReportEvidenceResponse]
    created_at: datetime
    updated_at: datetime


class ReportListResponse(BaseModel):
    items: list[ReportResponse]
    next_cursor: str | None
