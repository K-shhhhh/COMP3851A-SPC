"""PostgreSQL persistence adapter for privacy-preserving user reports."""

from __future__ import annotations

import base64
import binascii
import json
import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unicodedata import normalize

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.reports.domain.exceptions import (
    DuplicateReportError,
    InvalidEvidenceError,
    ReportNotFoundError,
    ReportPermissionDeniedError,
)
from app.domains.reports.domain.models import (
    EvidenceUpload,
    Report,
    ReportCategory,
    ReportEvidence,
    ReportPage,
    ReportStatus,
    ReportTargetType,
)
from app.domains.reports.domain.repository import ReportRepository
from app.models.orm_models import (
    ActivityStatus,
    Attachment as ORMAttachment,
    Channel as ORMChannel,
    Evidence as ORMEvidence,
    Group as ORMGroup,
    GroupType,
    Membership as ORMMembership,
    Message as ORMMessage,
    ReportActivityAction as ORMReportActivityAction,
    ReportActivityEvent as ORMReportActivityEvent,
    ReportCategory as ORMReportCategory,
    ReportStatus as ORMReportStatus,
    ReportTargetType as ORMReportTargetType,
    User as ORMUser,
    UserReport as ORMUserReport,
)

_ACTIVE_REPORT_STATUSES = (
    ORMReportStatus.SUBMITTED,
    ORMReportStatus.UNDER_REVIEW,
)
_STUDY_GROUP_TYPES = (GroupType.PUBLIC, GroupType.PRIVATE)
_FORBIDDEN_SNAPSHOT_KEYS = frozenset(
    {
        "file_path",
        "object_path",
        "private_storage_key",
        "password",
        "password_hash",
        "access_token",
        "refresh_token",
    }
)
_DUPLICATE_ACTIVE_REPORT_CONSTRAINTS = (
    "uq_user_reports_active_reporter_message",
    "uq_user_reports_active_reporter_group",
    "uq_user_reports_active_reporter_file",
)


class PostgreSQLReportRepository(ReportRepository):
    """Persist user reports with server-side snapshots and strict submitter scoping."""

    LIMITED_CONTEXT_WINDOW_EACH_SIDE = 2
    MAX_EVIDENCE_FILES = 3
    MAX_EVIDENCE_BYTES = 5 * 1024 * 1024
    ALLOWED_EVIDENCE_TYPES = frozenset({"image/jpeg", "image/png"})

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._session = session

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
        """Validate target access and atomically persist snapshots, report, and evidence metadata."""

        reporter_uuid = self._parse_uuid(reporter_user_id)
        if reporter_uuid is None:
            raise ReportPermissionDeniedError(
                "Authenticated reporter account is invalid."
            )

        cleaned_target_id = target_id.strip()
        if not cleaned_target_id:
            raise ReportNotFoundError("The report target was not found.")

        cleaned_description = description.strip()
        if len(cleaned_description) < 10 or len(cleaned_description) > 2000:
            raise ValueError(
                "Description must contain between 10 and 2000 characters."
            )

        self._validate_evidence_uploads(evidence)

        try:
            reporter = await self._session.scalar(
                select(ORMUser)
                .where(
                    ORMUser.user_id == reporter_uuid,
                    ORMUser.deleted_at.is_(None),
                    ORMUser.status == ActivityStatus.ACTIVE,
                )
                .with_for_update(read=True)
            )
            if reporter is None:
                raise ReportPermissionDeniedError(
                    "Inactive or missing accounts cannot submit reports."
                )

            target_message_id: int | None = None
            target_group_id: uuid.UUID | None = None
            target_file_id: int | None = None
            target_snapshot: dict[str, object]
            limited_context_snapshot: list[dict[str, object]] = []

            if target_type == ReportTargetType.MESSAGE:
                (
                    target_message_id,
                    target_snapshot,
                    limited_context_snapshot,
                ) = await self._validate_and_snapshot_message(
                    reporter_uuid=reporter_uuid,
                    raw_target_id=cleaned_target_id,
                    include_limited_context=include_limited_context,
                )
            elif target_type == ReportTargetType.GROUP:
                (
                    target_group_id,
                    target_snapshot,
                ) = await self._validate_and_snapshot_group(
                    reporter_uuid=reporter_uuid,
                    raw_target_id=cleaned_target_id,
                )
            elif target_type == ReportTargetType.FILE:
                (
                    target_file_id,
                    target_snapshot,
                ) = await self._validate_and_snapshot_file(
                    reporter_uuid=reporter_uuid,
                    raw_target_id=cleaned_target_id,
                )
            else:
                raise ValueError(f"Unsupported report target_type: {target_type!r}")

            now = datetime.now(timezone.utc)
            report_uuid = uuid.uuid4()

            orm_report = ORMUserReport(
                report_id=report_uuid,
                reporter_user_id=reporter_uuid,
                target_type=ORMReportTargetType(target_type.value),
                target_message_id=target_message_id,
                target_group_id=target_group_id,
                target_file_id=target_file_id,
                description=cleaned_description,
                category=ORMReportCategory(category.value),
                status=ORMReportStatus.SUBMITTED,
                target_snapshot=target_snapshot,
                limited_context_snapshot=limited_context_snapshot,
                created_at=now,
                last_updated_at=now,
            )
            self._session.add(orm_report)
            await self._session.flush()

            orm_evidence_items: list[ORMEvidence] = []
            for upload in evidence:
                evidence_uuid = uuid.uuid4()
                safe_filename = self._sanitize_evidence_filename(
                    upload.filename, upload.content_type
                )
                # NEXT UPDATE (Private Evidence Object Storage):
                # Private evidence storage implementations are not ready yet.
                # When the private object-storage adapter (e.g. EvidenceStorage)
                # is implemented in the next update:
                # 1. Inject the private storage port into PostgreSQLReportRepository
                #    (never store proof images under a public bucket or public URL).
                # 2. Persist ``upload.content`` bytes under a backend-generated
                #    opaque key (such as ``private_storage_key`` below) before
                #    committing the database transaction.
                # 3. Coordinate rollback/compensation (delete staged private
                #    blobs if PostgreSQL commit fails, or sweep staged keys via
                #    an idempotent cleanup/outbox worker) so orphaned files do
                #    not remain in private storage.
                # 4. Continue omitting ``private_storage_key`` from all domain
                #    and HTTP responses.
                private_storage_key = (
                    f"private/reports/{report_uuid}/evidence/{evidence_uuid}"
                )
                orm_evidence = ORMEvidence(
                    evidence_id=evidence_uuid,
                    report_id=report_uuid,
                    private_storage_key=private_storage_key,
                    file_name=safe_filename,
                    file_type=upload.content_type,
                    file_size_bytes=len(upload.content),
                    created_at=now,
                )
                self._session.add(orm_evidence)
                orm_evidence_items.append(orm_evidence)

            orm_activity = ORMReportActivityEvent(
                activity_event_id=uuid.uuid4(),
                report_id=report_uuid,
                actor_type=reporter.user_role,
                actor_id=reporter_uuid,
                action=ORMReportActivityAction.REPORT_SUBMITTED,
                summary="Report submitted.",
                event_timestamp=now,
            )
            self._session.add(orm_activity)

            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            if self._is_duplicate_active_report_violation(exc):
                raise DuplicateReportError(
                    "You already have an active report for this target."
                ) from exc
            raise
        except Exception:
            await self._session.rollback()
            raise

        return self._to_domain_report(orm_report, orm_evidence_items)

    async def list_reports(
        self,
        *,
        reporter_user_id: str,
        status: ReportStatus | None,
        cursor: str | None,
        limit: int,
    ) -> ReportPage:
        """List reports scoped strictly to the authenticated reporter."""

        if limit < 1:
            raise ValueError("limit must be at least 1.")

        cursor_position = (
            self._decode_cursor(cursor) if cursor is not None else None
        )

        reporter_uuid = self._parse_uuid(reporter_user_id)
        if reporter_uuid is None:
            return ReportPage(items=[], next_cursor=None)

        conditions = [ORMUserReport.reporter_user_id == reporter_uuid]
        if status is not None:
            conditions.append(
                ORMUserReport.status == ORMReportStatus(status.value)
            )
        if cursor_position is not None:
            cursor_created_at, cursor_report_id = cursor_position
            conditions.append(
                or_(
                    ORMUserReport.created_at < cursor_created_at,
                    and_(
                        ORMUserReport.created_at == cursor_created_at,
                        ORMUserReport.report_id < cursor_report_id,
                    ),
                )
            )

        rows = list(
            (
                await self._session.scalars(
                    select(ORMUserReport)
                    .where(*conditions)
                    .order_by(
                        ORMUserReport.created_at.desc(),
                        ORMUserReport.report_id.desc(),
                    )
                    .limit(limit + 1)
                )
            ).all()
        )

        has_more = len(rows) > limit
        page_rows = rows[:limit]
        next_cursor = (
            self._encode_cursor(
                page_rows[-1].created_at, page_rows[-1].report_id
            )
            if has_more and page_rows
            else None
        )

        evidence_by_report = await self._load_evidence_map(
            [row.report_id for row in page_rows]
        )
        items = [
            self._to_domain_report(
                row, evidence_by_report.get(row.report_id, [])
            )
            for row in page_rows
        ]
        return ReportPage(items=items, next_cursor=next_cursor)

    async def get_report(
        self,
        *,
        reporter_user_id: str,
        report_id: str,
    ) -> Report | None:
        """Return one report only when owned by ``reporter_user_id``."""

        reporter_uuid = self._parse_uuid(reporter_user_id)
        report_uuid = self._parse_uuid(report_id)
        if reporter_uuid is None or report_uuid is None:
            return None

        row = await self._session.scalar(
            select(ORMUserReport).where(
                ORMUserReport.report_id == report_uuid,
                ORMUserReport.reporter_user_id == reporter_uuid,
            )
        )
        if row is None:
            return None

        evidence_rows = list(
            (
                await self._session.scalars(
                    select(ORMEvidence)
                    .where(ORMEvidence.report_id == report_uuid)
                    .order_by(
                        ORMEvidence.created_at.asc(),
                        ORMEvidence.evidence_id.asc(),
                    )
                )
            ).all()
        )
        return self._to_domain_report(row, evidence_rows)

    async def _validate_and_snapshot_message(
        self,
        *,
        reporter_uuid: uuid.UUID,
        raw_target_id: str,
        include_limited_context: bool,
    ) -> tuple[int, dict[str, object], list[dict[str, object]]]:
        message_id = self._parse_positive_int(raw_target_id)
        if message_id is None:
            raise ReportNotFoundError("The reported message was not found.")

        row = (
            await self._session.execute(
                select(ORMMessage, ORMChannel, ORMGroup)
                .join(
                    ORMChannel, ORMChannel.channel_id == ORMMessage.channel_id
                )
                .join(ORMGroup, ORMGroup.group_id == ORMChannel.group_id)
                .where(
                    ORMMessage.message_id == message_id,
                    ORMMessage.deleted_at.is_(None),
                    ORMChannel.deleted_at.is_(None),
                    ORMGroup.deleted_at.is_(None),
                    ORMGroup.group_type.in_(_STUDY_GROUP_TYPES),
                )
                .with_for_update(read=True, of=ORMMessage)
            )
        ).first()
        if row is None:
            raise ReportNotFoundError("The reported message was not found.")

        message, channel, group = row

        membership_id = await self._session.scalar(
            select(ORMMembership.membership_id).where(
                ORMMembership.group_id == group.group_id,
                ORMMembership.user_id == reporter_uuid,
            )
        )
        if membership_id is None:
            raise ReportPermissionDeniedError(
                "You do not have permission to report messages in this study group."
            )

        await self._ensure_no_active_duplicate(
            reporter_uuid=reporter_uuid,
            target_column=ORMUserReport.target_message_id,
            target_value=message.message_id,
        )

        # Build an immutable server-side snapshot; never trust browser text.
        target_snapshot: dict[str, object] = {
            "user_id": str(message.user_id),
            "message_text": message.message_content,
            "sent_timestamp": message.sent_at.isoformat(),
        }

        limited_context_snapshot: list[dict[str, object]] = []
        if include_limited_context:
            limited_context_snapshot = await self._capture_nearby_messages(
                channel_id=channel.channel_id,
                anchor_sent_at=message.sent_at,
                anchor_message_id=message.message_id,
            )

        return message.message_id, target_snapshot, limited_context_snapshot

    async def _capture_nearby_messages(
        self,
        *,
        channel_id: uuid.UUID,
        anchor_sent_at: datetime,
        anchor_message_id: int,
    ) -> list[dict[str, object]]:
        """Capture at most 2 active messages before and 2 after in the same channel."""

        window = self.LIMITED_CONTEXT_WINDOW_EACH_SIDE

        before_rows = list(
            (
                await self._session.scalars(
                    select(ORMMessage)
                    .where(
                        ORMMessage.channel_id == channel_id,
                        ORMMessage.deleted_at.is_(None),
                        or_(
                            ORMMessage.sent_at < anchor_sent_at,
                            and_(
                                ORMMessage.sent_at == anchor_sent_at,
                                ORMMessage.message_id < anchor_message_id,
                            ),
                        ),
                    )
                    .order_by(
                        ORMMessage.sent_at.desc(),
                        ORMMessage.message_id.desc(),
                    )
                    .limit(window)
                )
            ).all()
        )
        before_rows.reverse()

        after_rows = list(
            (
                await self._session.scalars(
                    select(ORMMessage)
                    .where(
                        ORMMessage.channel_id == channel_id,
                        ORMMessage.deleted_at.is_(None),
                        or_(
                            ORMMessage.sent_at > anchor_sent_at,
                            and_(
                                ORMMessage.sent_at == anchor_sent_at,
                                ORMMessage.message_id > anchor_message_id,
                            ),
                        ),
                    )
                    .order_by(
                        ORMMessage.sent_at.asc(),
                        ORMMessage.message_id.asc(),
                    )
                    .limit(window)
                )
            ).all()
        )

        return [
            {
                "message_id": item.message_id,
                "user_id": str(item.user_id),
                "message_text": item.message_content,
                "sent_timestamp": item.sent_at.isoformat(),
            }
            for item in (*before_rows, *after_rows)
        ]

    async def _validate_and_snapshot_group(
        self,
        *,
        reporter_uuid: uuid.UUID,
        raw_target_id: str,
    ) -> tuple[uuid.UUID, dict[str, object]]:
        group_uuid = self._parse_uuid(raw_target_id)
        if group_uuid is None:
            raise ReportNotFoundError("The reported study group was not found.")

        group = await self._session.scalar(
            select(ORMGroup)
            .where(
                ORMGroup.group_id == group_uuid,
                ORMGroup.deleted_at.is_(None),
                ORMGroup.group_type.in_(_STUDY_GROUP_TYPES),
            )
            .with_for_update(read=True)
        )
        if group is None:
            raise ReportNotFoundError("The reported study group was not found.")

        if group.group_type == GroupType.PRIVATE:
            membership_id = await self._session.scalar(
                select(ORMMembership.membership_id).where(
                    ORMMembership.group_id == group.group_id,
                    ORMMembership.user_id == reporter_uuid,
                )
            )
            if membership_id is None:
                raise ReportPermissionDeniedError(
                    "You do not have permission to report this private study group."
                )

        await self._ensure_no_active_duplicate(
            reporter_uuid=reporter_uuid,
            target_column=ORMUserReport.target_group_id,
            target_value=group.group_id,
        )

        last_updated = group.last_updated_at or group.created_at
        target_snapshot: dict[str, object] = {
            "current_owner_id": str(group.current_owner),
            "group_name": group.group_name,
            "last_updated_timestamp": last_updated.isoformat(),
        }
        return group.group_id, target_snapshot

    async def _validate_and_snapshot_file(
        self,
        *,
        reporter_uuid: uuid.UUID,
        raw_target_id: str,
    ) -> tuple[int, dict[str, object]]:
        attachment_id = self._parse_positive_int(raw_target_id)
        if attachment_id is None:
            raise ReportNotFoundError("The reported file was not found.")

        # Only active study-group channel attachments are reportable; personal
        # notes and personal-chat uploads are excluded from user reports.
        row = (
            await self._session.execute(
                select(ORMAttachment, ORMChannel, ORMGroup)
                .join(
                    ORMChannel,
                    ORMChannel.channel_id == ORMAttachment.channel_id,
                )
                .join(ORMGroup, ORMGroup.group_id == ORMAttachment.group_id)
                .where(
                    ORMAttachment.attachment_id == attachment_id,
                    ORMAttachment.deleted_at.is_(None),
                    ORMAttachment.channel_id.is_not(None),
                    ORMAttachment.group_id.is_not(None),
                    ORMChannel.deleted_at.is_(None),
                    ORMGroup.deleted_at.is_(None),
                    ORMGroup.group_type.in_(_STUDY_GROUP_TYPES),
                )
                .with_for_update(read=True, of=ORMAttachment)
            )
        ).first()
        if row is None:
            raise ReportNotFoundError("The reported file was not found.")

        attachment, _channel, group = row

        membership_id = await self._session.scalar(
            select(ORMMembership.membership_id).where(
                ORMMembership.group_id == group.group_id,
                ORMMembership.user_id == reporter_uuid,
            )
        )
        if membership_id is None:
            raise ReportPermissionDeniedError(
                "You do not have permission to report files in this study group."
            )

        await self._ensure_no_active_duplicate(
            reporter_uuid=reporter_uuid,
            target_column=ORMUserReport.target_file_id,
            target_value=attachment.attachment_id,
        )

        # Store attachment_id instead of object_path/file_path so private
        # object-storage paths are never persisted in snapshots or returned.
        target_snapshot: dict[str, object] = {
            "user_id": str(attachment.uploaded_by),
            "attachment_id": attachment.attachment_id,
            "sent_timestamp": attachment.uploaded_at.isoformat(),
        }
        return attachment.attachment_id, target_snapshot

    async def _ensure_no_active_duplicate(
        self,
        *,
        reporter_uuid: uuid.UUID,
        target_column: Any,
        target_value: Any,
    ) -> None:
        existing_id = await self._session.scalar(
            select(ORMUserReport.report_id).where(
                ORMUserReport.reporter_user_id == reporter_uuid,
                target_column == target_value,
                ORMUserReport.status.in_(_ACTIVE_REPORT_STATUSES),
            )
        )
        if existing_id is not None:
            raise DuplicateReportError(
                "You already have an active report for this target."
            )

    async def _load_evidence_map(
        self,
        report_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, list[ORMEvidence]]:
        if not report_ids:
            return {}
        rows = (
            await self._session.scalars(
                select(ORMEvidence)
                .where(ORMEvidence.report_id.in_(report_ids))
                .order_by(
                    ORMEvidence.created_at.asc(),
                    ORMEvidence.evidence_id.asc(),
                )
            )
        ).all()
        grouped: dict[uuid.UUID, list[ORMEvidence]] = defaultdict(list)
        for item in rows:
            grouped[item.report_id].append(item)
        return grouped

    @classmethod
    def _validate_evidence_uploads(
        cls,
        evidence: list[EvidenceUpload],
    ) -> None:
        if len(evidence) > cls.MAX_EVIDENCE_FILES:
            raise InvalidEvidenceError(
                "A report can include at most three proof images."
            )
        for item in evidence:
            if item.content_type not in cls.ALLOWED_EVIDENCE_TYPES:
                raise InvalidEvidenceError(
                    "Proof must be a PNG or JPEG image."
                )
            if not item.content or len(item.content) > cls.MAX_EVIDENCE_BYTES:
                raise InvalidEvidenceError(
                    "Each proof image must be between 1 byte and 5 MB."
                )
            if not cls._has_valid_image_signature(item):
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

    @staticmethod
    def _sanitize_evidence_filename(filename: str, content_type: str) -> str:
        default_ext = ".png" if content_type == "image/png" else ".jpg"
        candidate = normalize("NFKC", filename or "").strip()
        candidate = candidate.replace("\\", "/").split("/")[-1]
        safe_name = re.sub(r"[^\w.()\- ]", "_", candidate).strip(" .")
        safe_name = re.sub(r"\s+", " ", safe_name)
        if not safe_name:
            return f"proof-image{default_ext}"
        suffix = Path(safe_name).suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg"}:
            safe_name = f"{safe_name[:240].rstrip(' .')}{default_ext}"
        elif len(safe_name) > 255:
            stem = Path(safe_name).stem[: 255 - len(suffix)].rstrip(" .")
            safe_name = f"{stem}{suffix}"
        return safe_name

    @classmethod
    def _to_domain_report(
        cls,
        row: ORMUserReport,
        evidence_rows: list[ORMEvidence],
    ) -> Report:
        return Report(
            report_id=str(row.report_id),
            reporter_user_id=str(row.reporter_user_id),
            target_type=ReportTargetType(row.target_type.value),
            target_id=cls._extract_target_id(row),
            category=ReportCategory(row.category.value),
            description=row.description,
            status=ReportStatus(row.status.value),
            target_snapshot=cls._sanitize_target_snapshot(row),
            limited_context_snapshot=cls._sanitize_limited_context_snapshot(
                row.limited_context_snapshot
            ),
            evidence=[
                ReportEvidence(
                    evidence_id=str(ev.evidence_id),
                    filename=ev.file_name,
                    content_type=ev.file_type,
                )
                for ev in evidence_rows
            ],
            created_at=row.created_at,
            updated_at=row.last_updated_at or row.created_at,
        )

    @staticmethod
    def _extract_target_id(row: ORMUserReport) -> str:
        if row.target_type == ORMReportTargetType.MESSAGE:
            if row.target_message_id is None:
                raise ValueError("Message report is missing target_message_id.")
            return str(row.target_message_id)
        if row.target_type == ORMReportTargetType.GROUP:
            if row.target_group_id is None:
                raise ValueError("Group report is missing target_group_id.")
            return str(row.target_group_id)
        if row.target_type == ORMReportTargetType.FILE:
            if row.target_file_id is None:
                raise ValueError("File report is missing target_file_id.")
            return str(row.target_file_id)
        raise ValueError(f"Unsupported report target_type: {row.target_type!r}")

    @staticmethod
    def _sanitize_target_snapshot(row: ORMUserReport) -> dict[str, object]:
        raw = row.target_snapshot if isinstance(row.target_snapshot, dict) else {}
        sanitized: dict[str, object] = {
            str(key): value
            for key, value in raw.items()
            if str(key) not in _FORBIDDEN_SNAPSHOT_KEYS
        }
        if (
            row.target_type == ORMReportTargetType.FILE
            and "attachment_id" not in sanitized
            and "file_id" not in sanitized
            and row.target_file_id is not None
        ):
            sanitized["attachment_id"] = row.target_file_id
        return sanitized

    @staticmethod
    def _sanitize_limited_context_snapshot(
        raw: list[dict[str, Any]] | dict[str, Any] | None,
    ) -> list[dict[str, object]]:
        if not isinstance(raw, list):
            return []
        sanitized_items: list[dict[str, object]] = []
        for entry in raw:
            if isinstance(entry, dict):
                sanitized_items.append(
                    {
                        str(key): value
                        for key, value in entry.items()
                        if str(key) not in _FORBIDDEN_SNAPSHOT_KEYS
                    }
                )
        return sanitized_items

    @staticmethod
    def _encode_cursor(created_at: datetime, report_id: uuid.UUID) -> str:
        payload = json.dumps(
            {
                "v": 1,
                "created_at": created_at.isoformat(),
                "report_id": str(report_id),
            },
            separators=(",", ":"),
        ).encode("utf-8")
        return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")

    @classmethod
    def _decode_cursor(cls, cursor: str) -> tuple[datetime, uuid.UUID]:
        cleaned = cursor.strip()
        if not cleaned:
            raise ValueError("Invalid pagination cursor.")
        padding = "=" * (-len(cleaned) % 4)
        try:
            decoded = base64.urlsafe_b64decode(cleaned + padding).decode("utf-8")
            payload = json.loads(decoded)
        except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid pagination cursor.") from exc

        if not isinstance(payload, dict) or payload.get("v") != 1:
            raise ValueError("Invalid pagination cursor.")

        raw_created_at = payload.get("created_at")
        raw_report_id = payload.get("report_id")
        if not isinstance(raw_created_at, str) or not isinstance(
            raw_report_id, str
        ):
            raise ValueError("Invalid pagination cursor.")

        try:
            created_at = datetime.fromisoformat(raw_created_at)
        except ValueError as exc:
            raise ValueError("Invalid pagination cursor.") from exc
        if created_at.tzinfo is None:
            raise ValueError("Invalid pagination cursor.")

        report_uuid = cls._parse_uuid(raw_report_id)
        if report_uuid is None:
            raise ValueError("Invalid pagination cursor.")

        return created_at, report_uuid

    @staticmethod
    def _is_duplicate_active_report_violation(exc: IntegrityError) -> bool:
        diag = getattr(exc.orig, "diag", None)
        constraint_name = getattr(diag, "constraint_name", None)
        if constraint_name in _DUPLICATE_ACTIVE_REPORT_CONSTRAINTS:
            return True
        message = str(exc.orig or exc).lower()
        return any(
            name in message for name in _DUPLICATE_ACTIVE_REPORT_CONSTRAINTS
        )

    @staticmethod
    def _parse_uuid(value: str) -> uuid.UUID | None:
        try:
            return uuid.UUID(str(value).strip())
        except (TypeError, ValueError, AttributeError):
            return None

    @staticmethod
    def _parse_positive_int(value: str) -> int | None:
        cleaned = value.strip()
        if not cleaned or not cleaned.isdigit():
            return None
        parsed = int(cleaned)
        return parsed if parsed > 0 else None
