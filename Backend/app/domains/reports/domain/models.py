"""Privacy-preserving report domain objects."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ReportTargetType(StrEnum):
    MESSAGE = "message"
    GROUP = "group"
    FILE = "file"


class ReportCategory(StrEnum):
    HARASSMENT_BULLYING = "harassment_bullying"
    HATE_DISCRIMINATION = "hate_discrimination"
    SPAM_SCAM = "spam_scam"
    INAPPROPRIATE_CONTENT = "inappropriate_content"
    ACADEMIC_MISCONDUCT = "academic_misconduct"
    PRIVACY_VIOLATION = "privacy_violation"
    IMPERSONATION = "impersonation"
    DANGEROUS_CONTENT = "dangerous_content"
    OTHER = "other"


class ReportStatus(StrEnum):
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


@dataclass(frozen=True, slots=True)
class EvidenceUpload:
    filename: str
    content_type: str
    content: bytes


@dataclass(frozen=True, slots=True)
class ReportEvidence:
    evidence_id: str
    filename: str
    content_type: str


@dataclass(frozen=True, slots=True)
class Report:
    report_id: str
    reporter_user_id: str
    target_type: ReportTargetType
    target_id: str
    category: ReportCategory
    description: str
    status: ReportStatus
    target_snapshot: dict[str, object]
    limited_context_snapshot: list[dict[str, object]]
    evidence: list[ReportEvidence]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ReportPage:
    items: list[Report]
    next_cursor: str | None
