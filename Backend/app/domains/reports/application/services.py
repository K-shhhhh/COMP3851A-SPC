"""Validated, privacy-aware user-report use cases."""

from app.domains.reports.domain.exceptions import InvalidEvidenceError, ReportNotFoundError
from app.domains.reports.domain.models import (
    EvidenceUpload,
    Report,
    ReportCategory,
    ReportPage,
    ReportStatus,
    ReportTargetType,
)
from app.domains.reports.domain.repository import ReportRepository


class ReportService:
    MAX_EVIDENCE_FILES = 3
    MAX_EVIDENCE_BYTES = 5 * 1024 * 1024
    ALLOWED_EVIDENCE_TYPES = {"image/jpeg", "image/png"}

    def __init__(self, repository: ReportRepository) -> None:
        self.repository = repository

    async def create_report(
        self,
        *,
        reporter_user_id: str,
        target_type: ReportTargetType,
        target_id: str,
        category: ReportCategory,
        description: str,
        include_limited_context: bool,
        evidence: list[EvidenceUpload],
    ) -> Report:
        cleaned_target_id = target_id.strip()
        cleaned_description = description.strip()
        if not cleaned_target_id:
            raise ReportNotFoundError("The report target was not found.")
        if len(cleaned_description) < 10 or len(cleaned_description) > 2000:
            raise ValueError("Description must contain between 10 and 2000 characters.")
        self._validate_evidence(evidence)
        return await self.repository.create_report(
            reporter_user_id=reporter_user_id,
            target_type=target_type,
            target_id=cleaned_target_id,
            category=category,
            description=cleaned_description,
            include_limited_context=include_limited_context,
            evidence=evidence,
        )

    async def list_reports(
        self,
        *,
        reporter_user_id: str,
        status: ReportStatus | None,
        cursor: str | None,
        limit: int,
    ) -> ReportPage:
        return await self.repository.list_reports(
            reporter_user_id=reporter_user_id,
            status=status,
            cursor=cursor,
            limit=limit,
        )

    async def get_report(self, *, reporter_user_id: str, report_id: str) -> Report:
        report = await self.repository.get_report(
            reporter_user_id=reporter_user_id,
            report_id=report_id,
        )
        if report is None:
            raise ReportNotFoundError("The report was not found.")
        return report

    def _validate_evidence(self, evidence: list[EvidenceUpload]) -> None:
        if len(evidence) > self.MAX_EVIDENCE_FILES:
            raise InvalidEvidenceError("A report can include at most three proof images.")
        for item in evidence:
            if item.content_type not in self.ALLOWED_EVIDENCE_TYPES:
                raise InvalidEvidenceError("Proof must be a PNG or JPEG image.")
            if not item.content or len(item.content) > self.MAX_EVIDENCE_BYTES:
                raise InvalidEvidenceError("Each proof image must be between 1 byte and 5 MB.")
            if not self._has_valid_image_signature(item):
                raise InvalidEvidenceError(
                    "Proof file contents do not match the declared image type."
                )

    @staticmethod
    def _has_valid_image_signature(item: EvidenceUpload) -> bool:
        if item.content_type == "image/png":
            return item.content.startswith(b"\x89PNG\r\n\x1a\n")
        if item.content_type == "image/jpeg":
            return item.content.startswith(b"\xff\xd8\xff")
        return False
