"""PostgreSQL persistence adapter for administration and report governance."""

from __future__ import annotations

import base64
import binascii
import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.domains.administration.domain.exceptions import (
    AdministrationConflictError,
    AdministrationResourceNotFoundError,
    AdministrationValidationError,
)
from app.domains.administration.domain.models import (
    AdminAttachmentDetails,
    AdminAttachmentFile,
    AdminAttachmentPage,
    AdminAttachmentSummary,
    AdminAuditEvent,
    AdminAuditEventPage,
    AdminEvidenceFile,
    AdminGroupChannel,
    AdminGroupDetails,
    AdminGroupPage,
    AdminGroupSummary,
    AdminReportActivity,
    AdminReportActivityType,
    AdminReportDetails,
    AdminReportEvidence,
    AdminReportGovernanceAction,
    AdminReportPage,
    AdminReportResolutionOutcome,
    AdminReportSummary,
    AdminUserDetails,
    AdminUserPage,
    AdminUserSummary,
    AdministrationActor,
    AdministrationAttachmentSource,
    AdministrationAttachmentStatus,
    AdministrationGroupStatus,
    AdministrationGroupVisibility,
    AdministrationUserRole,
    AdministrationUserStatus,
    DashboardSnapshot,
    GovernanceActionResult,
    ProcessingFailure,
)
from app.domains.administration.domain.repository import (
    AdministrationRepository,
)
from app.domains.notes.domain.exceptions import AttachmentStorageError
from app.domains.notes.domain.processing import AttachmentProcessingDispatcher
from app.domains.notes.domain.storage import AttachmentStorage
from app.domains.reports.domain.models import (
    ReportCategory,
    ReportStatus,
    ReportTargetType,
)
from app.domains.reports.domain.storage import EvidenceStorage, EvidenceStorageError
from app.models.orm_models import (
    ActivityStatus,
    Attachment as ORMAttachment,
    AttachmentStatus,
    AuditEvent as ORMAuditEvent,
    Channel as ORMChannel,
    Chunk as ORMChunk,
    Evidence as ORMEvidence,
    Group as ORMGroup,
    GroupType,
    KnowledgeEdge as ORMKnowledgeEdge,
    KnowledgeGraph as ORMKnowledgeGraph,
    KnowledgeNode as ORMKnowledgeNode,
    MemberRole,
    Membership as ORMMembership,
    Message as ORMMessage,
    ReportActivityAction as ORMReportActivityAction,
    ReportActivityEvent as ORMReportActivityEvent,
    ReportNote as ORMReportNote,
    ReportOutcome as ORMReportOutcome,
    ReportStatus as ORMReportStatus,
    ReportTargetType as ORMReportTargetType,
    User as ORMUser,
    UserReport as ORMUserReport,
    UserRole as ORMUserRole,
)

logger = logging.getLogger(__name__)

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
_ALLOWED_GOVERNANCE_ACTIONS: dict[
    ORMReportTargetType, frozenset[AdminReportGovernanceAction]
] = {
    ORMReportTargetType.MESSAGE: frozenset(
        {
            AdminReportGovernanceAction.REMOVE_MESSAGE,
            AdminReportGovernanceAction.DEACTIVATE_MESSAGE_AUTHOR,
        }
    ),
    ORMReportTargetType.GROUP: frozenset(
        {AdminReportGovernanceAction.REMOVE_GROUP}
    ),
    ORMReportTargetType.FILE: frozenset(
        {AdminReportGovernanceAction.REMOVE_FILE}
    ),
}
_COMMON_OUTCOMES = frozenset(
    {
        AdminReportResolutionOutcome.NO_VIOLATION,
        AdminReportResolutionOutcome.DUPLICATE,
        AdminReportResolutionOutcome.INSUFFICIENT_EVIDENCE,
    }
)
_ALLOWED_RESOLUTION_OUTCOMES: dict[
    ORMReportTargetType, frozenset[AdminReportResolutionOutcome]
] = {
    ORMReportTargetType.MESSAGE: _COMMON_OUTCOMES
    | frozenset(
        {
            AdminReportResolutionOutcome.CONTENT_REMOVED,
            AdminReportResolutionOutcome.USER_DEACTIVATED,
        }
    ),
    ORMReportTargetType.GROUP: _COMMON_OUTCOMES
    | frozenset({AdminReportResolutionOutcome.GROUP_REMOVED}),
    ORMReportTargetType.FILE: _COMMON_OUTCOMES
    | frozenset({AdminReportResolutionOutcome.FILE_REMOVED}),
}

_AUDIT_SERVICE_NAME = "administration.audit"
_AUDIT_SERVICE_ALIASES = frozenset(
    {
        "administration.audit",
        "administration",
        "audit",
        "audit_events",
    }
)

_CREDENTIAL_URI_RE = re.compile(
    r"\b[a-z][a-z0-9+.\-]*://[^\s\"']+", re.IGNORECASE
)
_BEARER_OR_JWT_RE = re.compile(
    r"(?:\bBearer\s+[A-Za-z0-9\-._~+/]+=*|\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,})",
    re.IGNORECASE,
)
_PASSWORD_HASH_RE = re.compile(r"\$(?:2[aby]|argon2(?:id|i|d)?)\$[^\s\"']+")
_WINDOWS_PATH_RE = re.compile(r"\b[A-Za-z]:\\(?:[^\\\s\"']+\\)*[^\\\s\"']+")
_POSIX_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9])/(?:var|tmp|etc|opt|usr|home|root|app|srv|private|storage)(?:/[^\s\"']+)+"
)


class PostgreSQLAdministrationRepository(AdministrationRepository):
    """Persist and query governance state using one request-scoped AsyncSession.

    When wiring ``get_administration_repository`` in ``app/api/dependencies.py``,
    pass ``attachment_storage=Depends(get_attachment_storage)`` and
    ``processing_dispatcher=Depends(get_attachment_processing_dispatcher)`` so
    attachment removal and retry coordinate with private PDF storage and Celery.
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        attachment_storage: AttachmentStorage | None = None,
        processing_dispatcher: AttachmentProcessingDispatcher | None = None,
        evidence_storage: EvidenceStorage | None = None,
    ) -> None:
        self.session = session
        self._session = session
        self._attachment_storage = attachment_storage
        self._processing_dispatcher = processing_dispatcher
        self._evidence_storage = evidence_storage

    async def get_dashboard(self) -> DashboardSnapshot:
        """Return concise administration metrics without operational health data."""

        now = datetime.now(timezone.utc)
        since = now - timedelta(hours=24)

        active_users = int(
            await self._session.scalar(
                select(func.count()).select_from(ORMUser).where(
                    ORMUser.deleted_at.is_(None),
                    ORMUser.status == ActivityStatus.ACTIVE,
                )
            )
            or 0
        )
        active_groups = int(
            await self._session.scalar(
                select(func.count()).select_from(ORMGroup).where(
                    ORMGroup.deleted_at.is_(None),
                    ORMGroup.group_type.in_(_STUDY_GROUP_TYPES),
                )
            )
            or 0
        )
        stored_notes = int(
            await self._session.scalar(
                select(func.count()).select_from(ORMAttachment).where(
                    ORMAttachment.deleted_at.is_(None)
                )
            )
            or 0
        )
        failure_conditions = (
            ORMAttachment.deleted_at.is_(None),
            ORMAttachment.processing_status == AttachmentStatus.FAILED,
            func.coalesce(
                ORMAttachment.processing_completed_at,
                ORMAttachment.last_updated_at,
                ORMAttachment.uploaded_at,
            )
            >= since,
        )
        processing_failures_24h = int(
            await self._session.scalar(
                select(func.count()).select_from(ORMAttachment).where(
                    *failure_conditions
                )
            )
            or 0
        )
        open_reports = int(
            await self._session.scalar(
                select(func.count()).select_from(ORMUserReport).where(
                    ORMUserReport.status.in_(
                        (ORMReportStatus.SUBMITTED, ORMReportStatus.UNDER_REVIEW)
                    )
                )
            )
            or 0
        )
        under_review_reports = int(
            await self._session.scalar(
                select(func.count()).select_from(ORMUserReport).where(
                    ORMUserReport.status == ORMReportStatus.UNDER_REVIEW
                )
            )
            or 0
        )
        recently_submitted_reports = int(
            await self._session.scalar(
                select(func.count()).select_from(ORMUserReport).where(
                    ORMUserReport.created_at >= since
                )
            )
            or 0
        )

        failure_rows = (
            await self._session.execute(
                select(ORMAttachment, ORMUser.fullname)
                .join(ORMUser, ORMUser.user_id == ORMAttachment.uploaded_by)
                .where(*failure_conditions)
                .order_by(
                    func.coalesce(
                        ORMAttachment.processing_completed_at,
                        ORMAttachment.last_updated_at,
                        ORMAttachment.uploaded_at,
                    ).desc(),
                    ORMAttachment.attachment_id.desc(),
                )
                .limit(5)
            )
        ).all()
        recent_failures = tuple(
            ProcessingFailure(
                attachment_id=attachment.attachment_id,
                title=attachment.title,
                file_name=attachment.file_name,
                uploader_name=uploader_name,
                safe_error=(
                    self._sanitize_operational_message(attachment.processing_error)
                    or "Processing failed."
                ),
                occurred_at=(
                    attachment.processing_completed_at
                    or attachment.last_updated_at
                    or attachment.uploaded_at
                ),
            )
            for attachment, uploader_name in failure_rows
        )

        audit_rows = (
            await self._session.execute(
                select(ORMAuditEvent, ORMUser.fullname)
                .join(ORMUser, ORMUser.user_id == ORMAuditEvent.admin_id)
                .order_by(
                    ORMAuditEvent.event_timestamp.desc(),
                    ORMAuditEvent.audit_event_id.desc(),
                )
                .limit(5)
            )
        ).all()
        recent_audit_events = tuple(
            self._to_audit_event(audit, admin_name)
            for audit, admin_name in audit_rows
        )

        report_rows = list(
            (
                await self._session.scalars(
                    select(ORMUserReport)
                    .order_by(
                        ORMUserReport.created_at.desc(),
                        ORMUserReport.report_id.desc(),
                    )
                    .limit(5)
                )
            ).all()
        )

        return DashboardSnapshot(
            active_users=active_users,
            active_study_groups=active_groups,
            stored_notes=stored_notes,
            processing_failures_24h=processing_failures_24h,
            open_reports=open_reports,
            under_review_reports=under_review_reports,
            recently_submitted_reports=recently_submitted_reports,
            recent_processing_failures=recent_failures,
            recent_audit_events=recent_audit_events,
            recent_reports=tuple(
                self._to_admin_report_summary(row) for row in report_rows
            ),
        )

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    async def list_users(
        self,
        *,
        search: str | None,
        status: AdministrationUserStatus | None,
        role: AdministrationUserRole | None,
        cursor: str | None,
        limit: int,
    ) -> AdminUserPage:
        """List non-deleted users with stable cursor pagination."""

        self._validate_limit(limit)
        cursor_pos = (
            self._decode_uuid_cursor(cursor, kind="users")
            if cursor is not None
            else None
        )

        conditions = [ORMUser.deleted_at.is_(None)]
        if status is not None:
            conditions.append(ORMUser.status == ActivityStatus(status.value))
        if role is not None:
            conditions.append(ORMUser.user_role == ORMUserRole(role.value))
        if search:
            pattern = self._like_pattern(search)
            search_clauses = [
                ORMUser.fullname.ilike(pattern, escape="\\"),
                ORMUser.email.ilike(pattern, escape="\\"),
            ]
            maybe_uuid = self._parse_uuid(search)
            if maybe_uuid is not None:
                search_clauses.append(ORMUser.user_id == maybe_uuid)
            conditions.append(or_(*search_clauses))
        if cursor_pos is not None:
            cursor_created_at, cursor_user_id = cursor_pos
            conditions.append(
                or_(
                    ORMUser.created_at < cursor_created_at,
                    and_(
                        ORMUser.created_at == cursor_created_at,
                        ORMUser.user_id < cursor_user_id,
                    ),
                )
            )

        rows = list(
            (
                await self._session.scalars(
                    select(ORMUser)
                    .where(*conditions)
                    .order_by(ORMUser.created_at.desc(), ORMUser.user_id.desc())
                    .limit(limit + 1)
                )
            ).all()
        )
        has_more = len(rows) > limit
        page_rows = rows[:limit]
        next_cursor = (
            self._encode_uuid_cursor(
                kind="users",
                timestamp=page_rows[-1].created_at,
                entity_id=page_rows[-1].user_id,
            )
            if has_more and page_rows
            else None
        )
        return AdminUserPage(
            items=tuple(self._to_user_summary(row) for row in page_rows),
            next_cursor=next_cursor,
        )

    async def get_user(self, user_id: str) -> AdminUserDetails | None:
        """Return safe user metadata and aggregate study-group/note counts."""

        user_uuid = self._parse_uuid(user_id)
        if user_uuid is None:
            return None

        user = await self._session.scalar(
            select(ORMUser).where(
                ORMUser.user_id == user_uuid,
                ORMUser.deleted_at.is_(None),
            )
        )
        if user is None:
            return None

        notes_count = int(
            await self._session.scalar(
                select(func.count())
                .select_from(ORMAttachment)
                .where(
                    ORMAttachment.uploaded_by == user_uuid,
                    ORMAttachment.show_in_library.is_(True),
                    ORMAttachment.deleted_at.is_(None),
                )
            )
            or 0
        )

        # groups_joined_count includes owned groups (all active non-personal
        # study-group memberships for this user).
        groups_joined_count = int(
            await self._session.scalar(
                select(func.count())
                .select_from(ORMMembership)
                .join(ORMGroup, ORMGroup.group_id == ORMMembership.group_id)
                .where(
                    ORMMembership.user_id == user_uuid,
                    ORMGroup.deleted_at.is_(None),
                    ORMGroup.group_type.in_(_STUDY_GROUP_TYPES),
                )
            )
            or 0
        )

        groups_owned_count = int(
            await self._session.scalar(
                select(func.count())
                .select_from(ORMGroup)
                .where(
                    ORMGroup.current_owner == user_uuid,
                    ORMGroup.deleted_at.is_(None),
                    ORMGroup.group_type.in_(_STUDY_GROUP_TYPES),
                )
            )
            or 0
        )

        return AdminUserDetails(
            user=self._to_user_summary(user),
            notes_count=notes_count,
            groups_joined_count=groups_joined_count,
            groups_owned_count=groups_owned_count,
        )

    async def count_active_administrators(self) -> int:
        """Count non-deleted active administrator accounts."""

        return int(
            await self._session.scalar(
                select(func.count())
                .select_from(ORMUser)
                .where(
                    ORMUser.deleted_at.is_(None),
                    ORMUser.user_role == ORMUserRole.ADMIN,
                    ORMUser.status == ActivityStatus.ACTIVE,
                )
            )
            or 0
        )

    async def create_user(
        self,
        *,
        full_name: str,
        email: str,
        password_hash: str,
        role: AdministrationUserRole,
        actor: AdministrationActor,
    ) -> AdminUserDetails:
        """Create an account and personal workspace with one audit event."""

        admin_uuid = self._require_valid_admin_uuid(actor.user_id)
        reason = self._require_valid_reason(actor.reason)
        now = datetime.now(timezone.utc)
        try:
            await self._require_active_admin_in_tx(admin_uuid)
            if await self._session.scalar(select(ORMUser.user_id).where(func.lower(ORMUser.email) == email.lower())):
                raise AdministrationConflictError("An account with this email already exists.")
            user = ORMUser(
                fullname=full_name,
                email=email,
                password_hash=password_hash,
                user_role=ORMUserRole(role.value),
                status=ActivityStatus.ACTIVE,
                created_at=now,
                email_verified_at=None,
                last_updated_at=now,
            )
            self._session.add(user)
            await self._session.flush()
            personal_group = ORMGroup(
                group_name=str(user.user_id),
                group_type=GroupType.PERSONAL,
                description="Personal AI Assistant",
                created_by=user.user_id,
                current_owner=user.user_id,
                max_members=1,
                created_at=now,
                last_updated_at=now,
            )
            self._session.add(personal_group)
            await self._session.flush()
            self._session.add(ORMMembership(
                user_id=user.user_id,
                group_id=personal_group.group_id,
                member_role=MemberRole.OWNER,
                joined_at=now,
            ))
            self._session.add(ORMAuditEvent(
                audit_event_id=uuid.uuid4(), admin_id=admin_uuid,
                action="create_user", target_type="user", target_id=str(user.user_id),
                reason=reason, event_timestamp=now,
            ))
            await self._session.commit()
        except AdministrationConflictError:
            await self._session.rollback()
            raise
        except IntegrityError as exc:
            await self._session.rollback()
            raise AdministrationConflictError("An account with this email already exists.") from exc
        except Exception:
            await self._session.rollback()
            raise
        created = await self.get_user(str(user.user_id))
        if created is None:
            raise AdministrationResourceNotFoundError("The created user could not be loaded.")
        return created

    async def update_user(
        self,
        *,
        user_id: str,
        full_name: str,
        email: str,
        actor: AdministrationActor,
    ) -> AdminUserDetails | None:
        """Lock an account, update its public identity, and audit atomically."""

        target_uuid = self._parse_uuid(user_id)
        if target_uuid is None:
            return None
        admin_uuid = self._require_valid_admin_uuid(actor.user_id)
        reason = self._require_valid_reason(actor.reason)
        now = datetime.now(timezone.utc)
        try:
            await self._require_active_admin_in_tx(admin_uuid)
            target = await self._session.scalar(
                select(ORMUser)
                .where(
                    ORMUser.user_id == target_uuid,
                    ORMUser.deleted_at.is_(None),
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if target is None:
                await self._session.rollback()
                return None
            duplicate = await self._session.scalar(
                select(ORMUser.user_id).where(
                    func.lower(ORMUser.email) == email.lower(),
                    ORMUser.user_id != target_uuid,
                )
            )
            if duplicate is not None:
                raise AdministrationConflictError("An account with this email already exists.")
            email_changed = target.email.casefold() != email.casefold()
            target.fullname = full_name
            target.email = email
            if email_changed:
                target.email_verified_at = None
            target.last_updated_at = now
            self._session.add(
                ORMAuditEvent(
                    audit_event_id=uuid.uuid4(),
                    admin_id=admin_uuid,
                    action="update_user",
                    target_type="user",
                    target_id=str(target_uuid),
                    reason=reason,
                    event_timestamp=now,
                )
            )
            await self._session.commit()
        except AdministrationConflictError:
            await self._session.rollback()
            raise
        except IntegrityError as exc:
            await self._session.rollback()
            raise AdministrationConflictError("An account with this email already exists.") from exc
        except Exception:
            await self._session.rollback()
            raise
        return await self.get_user(str(target_uuid))

    async def deactivate_user(
        self,
        *,
        user_id: str,
        actor: AdministrationActor,
    ) -> GovernanceActionResult | None:
        """Lock, revalidate user protections, deactivate, and audit atomically."""

        target_uuid = self._parse_uuid(user_id)
        if target_uuid is None:
            return None

        admin_uuid = self._require_valid_admin_uuid(actor.user_id)
        reason = self._require_valid_reason(actor.reason)

        if admin_uuid == target_uuid:
            raise AdministrationConflictError(
                "Administrators cannot deactivate their own account."
            )

        try:
            await self._require_active_admin_in_tx(admin_uuid)

            target = await self._lock_and_deactivate_user_in_tx(
                target_uuid=target_uuid,
                acting_admin_uuid=admin_uuid,
            )
            if target is None:
                await self._session.rollback()
                return None

            target_user, changed_at = target
            self._session.add(
                ORMAuditEvent(
                    audit_event_id=uuid.uuid4(),
                    admin_id=admin_uuid,
                    action="deactivate_user",
                    target_type="user",
                    target_id=str(target_user.user_id),
                    reason=reason,
                    event_timestamp=changed_at,
                )
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        return GovernanceActionResult(
            resource_id=str(target_user.user_id),
            status="deactivated",
            changed_at=changed_at,
        )

    async def reactivate_user(
        self,
        *,
        user_id: str,
        actor: AdministrationActor,
    ) -> GovernanceActionResult | None:
        """Lock, revalidate, reactivate a deactivated user, and audit atomically."""

        target_uuid = self._parse_uuid(user_id)
        if target_uuid is None:
            return None

        admin_uuid = self._require_valid_admin_uuid(actor.user_id)
        reason = self._require_valid_reason(actor.reason)

        try:
            await self._require_active_admin_in_tx(admin_uuid)

            target = await self._session.scalar(
                select(ORMUser)
                .where(
                    ORMUser.user_id == target_uuid,
                    ORMUser.deleted_at.is_(None),
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if target is None:
                await self._session.rollback()
                return None

            if target.status == ActivityStatus.ACTIVE:
                raise AdministrationConflictError(
                    "The account is already active."
                )

            now = datetime.now(timezone.utc)
            target.status = ActivityStatus.ACTIVE
            target.last_updated_at = now

            self._session.add(
                ORMAuditEvent(
                    audit_event_id=uuid.uuid4(),
                    admin_id=admin_uuid,
                    action="reactivate_user",
                    target_type="user",
                    target_id=str(target.user_id),
                    reason=reason,
                    event_timestamp=now,
                )
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        return GovernanceActionResult(
            resource_id=str(target.user_id),
            status="active",
            changed_at=now,
        )

    # ------------------------------------------------------------------
    # Study Groups
    # ------------------------------------------------------------------

    async def list_groups(
        self,
        *,
        search: str | None,
        visibility: AdministrationGroupVisibility | None,
        status: AdministrationGroupStatus | None,
        cursor: str | None,
        limit: int,
    ) -> AdminGroupPage:
        """List non-personal study groups with cursor pagination."""

        self._validate_limit(limit)
        cursor_pos = (
            self._decode_uuid_cursor(cursor, kind="groups")
            if cursor is not None
            else None
        )

        owner_alias = aliased(ORMUser)
        conditions = [ORMGroup.group_type.in_(_STUDY_GROUP_TYPES)]
        if visibility is not None:
            conditions.append(
                ORMGroup.group_type == GroupType(visibility.value)
            )
        if status == AdministrationGroupStatus.ACTIVE:
            conditions.append(ORMGroup.deleted_at.is_(None))
        elif status == AdministrationGroupStatus.REMOVED:
            conditions.append(ORMGroup.deleted_at.is_not(None))

        if search:
            pattern = self._like_pattern(search)
            search_clauses = [
                ORMGroup.group_name.ilike(pattern, escape="\\"),
                ORMGroup.description.ilike(pattern, escape="\\"),
                owner_alias.fullname.ilike(pattern, escape="\\"),
            ]
            maybe_uuid = self._parse_uuid(search)
            if maybe_uuid is not None:
                search_clauses.append(ORMGroup.group_id == maybe_uuid)
            conditions.append(or_(*search_clauses))

        if cursor_pos is not None:
            cursor_created_at, cursor_group_id = cursor_pos
            conditions.append(
                or_(
                    ORMGroup.created_at < cursor_created_at,
                    and_(
                        ORMGroup.created_at == cursor_created_at,
                        ORMGroup.group_id < cursor_group_id,
                    ),
                )
            )

        rows = list(
            (
                await self._session.execute(
                    select(ORMGroup, owner_alias.fullname)
                    .join(
                        owner_alias,
                        owner_alias.user_id == ORMGroup.current_owner,
                    )
                    .where(*conditions)
                    .order_by(
                        ORMGroup.created_at.desc(), ORMGroup.group_id.desc()
                    )
                    .limit(limit + 1)
                )
            ).all()
        )
        has_more = len(rows) > limit
        page_rows = rows[:limit]
        next_cursor = (
            self._encode_uuid_cursor(
                kind="groups",
                timestamp=page_rows[-1][0].created_at,
                entity_id=page_rows[-1][0].group_id,
            )
            if has_more and page_rows
            else None
        )

        group_ids = [grp.group_id for grp, _ in page_rows]
        member_counts = await self._load_group_member_counts(group_ids)
        channel_counts = await self._load_group_active_channel_counts(group_ids)

        items = tuple(
            self._to_group_summary(
                group=grp,
                owner_name=owner_name,
                member_count=member_counts.get(grp.group_id, 0),
                channel_count=channel_counts.get(grp.group_id, 0),
            )
            for grp, owner_name in page_rows
        )
        return AdminGroupPage(items=items, next_cursor=next_cursor)

    async def get_group(self, group_id: str) -> AdminGroupDetails | None:
        """Return governance metadata and channel names without chat messages."""

        group_uuid = self._parse_uuid(group_id)
        if group_uuid is None:
            return None

        owner_alias = aliased(ORMUser)
        creator_alias = aliased(ORMUser)
        row = (
            await self._session.execute(
                select(ORMGroup, owner_alias.fullname, creator_alias.fullname)
                .join(
                    owner_alias, owner_alias.user_id == ORMGroup.current_owner
                )
                .join(
                    creator_alias, creator_alias.user_id == ORMGroup.created_by
                )
                .where(
                    ORMGroup.group_id == group_uuid,
                    ORMGroup.group_type.in_(_STUDY_GROUP_TYPES),
                )
            )
        ).first()
        if row is None:
            return None

        grp, owner_name, creator_name = row

        role_rows = (
            await self._session.execute(
                select(ORMMembership.member_role, func.count())
                .where(ORMMembership.group_id == group_uuid)
                .group_by(ORMMembership.member_role)
            )
        ).all()
        role_counts = {role: int(cnt) for role, cnt in role_rows}
        owner_count = role_counts.get(MemberRole.OWNER, 0)
        admin_count = role_counts.get(MemberRole.ADMIN, 0)
        ordinary_member_count = role_counts.get(MemberRole.MEMBER, 0)
        member_count = owner_count + admin_count + ordinary_member_count

        channel_rows = list(
            (
                await self._session.scalars(
                    select(ORMChannel)
                    .where(
                        ORMChannel.group_id == group_uuid,
                        ORMChannel.deleted_at.is_(None),
                    )
                    .order_by(
                        ORMChannel.created_at.asc(),
                        ORMChannel.channel_id.asc(),
                    )
                )
            ).all()
        )
        channels = tuple(
            AdminGroupChannel(
                channel_id=str(ch.channel_id),
                name=ch.channel_name,
            )
            for ch in channel_rows
        )

        summary = self._to_group_summary(
            group=grp,
            owner_name=owner_name,
            member_count=member_count,
            channel_count=len(channels),
        )
        return AdminGroupDetails(
            group=summary,
            description=grp.description,
            max_members=grp.max_members,
            current_owner_id=str(grp.current_owner),
            created_by_id=str(grp.created_by),
            created_by_name=creator_name,
            owner_count=owner_count,
            admin_count=admin_count,
            ordinary_member_count=ordinary_member_count,
            channels=channels,
        )

    async def create_group(
        self,
        *,
        name: str,
        description: str | None,
        visibility: AdministrationGroupVisibility,
        max_members: int,
        owner_user_id: str,
        actor: AdministrationActor,
    ) -> AdminGroupDetails:
        """Create a Study Group and owner membership with an audit event."""

        admin_uuid = self._require_valid_admin_uuid(actor.user_id)
        owner_uuid = self._parse_uuid(owner_user_id)
        if owner_uuid is None:
            raise AdministrationValidationError("The selected owner ID is invalid.")
        reason = self._require_valid_reason(actor.reason)
        now = datetime.now(timezone.utc)
        try:
            await self._require_active_admin_in_tx(admin_uuid)
            owner = await self._session.scalar(
                select(ORMUser).where(
                    ORMUser.user_id == owner_uuid,
                    ORMUser.status == ActivityStatus.ACTIVE,
                    ORMUser.deleted_at.is_(None),
                ).with_for_update(read=True)
            )
            if owner is None:
                raise AdministrationConflictError("The selected owner is not active.")
            group = ORMGroup(
                group_name=name,
                group_type=GroupType(visibility.value),
                description=description,
                created_by=admin_uuid,
                current_owner=owner_uuid,
                max_members=max_members,
                created_at=now,
                last_updated_at=now,
            )
            self._session.add(group)
            await self._session.flush()
            self._session.add(ORMMembership(
                user_id=owner_uuid,
                group_id=group.group_id,
                member_role=MemberRole.OWNER,
                joined_at=now,
            ))
            self._session.add(ORMAuditEvent(
                audit_event_id=uuid.uuid4(), admin_id=admin_uuid,
                action="create_group", target_type="group", target_id=str(group.group_id),
                reason=reason, event_timestamp=now,
            ))
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        created = await self.get_group(str(group.group_id))
        if created is None:
            raise AdministrationResourceNotFoundError("The created study group could not be loaded.")
        return created

    async def update_group(
        self,
        *,
        group_id: str,
        name: str,
        description: str | None,
        visibility: AdministrationGroupVisibility,
        max_members: int,
        actor: AdministrationActor,
    ) -> AdminGroupDetails | None:
        """Lock a Study Group, update its metadata, and audit atomically."""

        group_uuid = self._parse_uuid(group_id)
        if group_uuid is None:
            return None
        admin_uuid = self._require_valid_admin_uuid(actor.user_id)
        reason = self._require_valid_reason(actor.reason)
        now = datetime.now(timezone.utc)
        try:
            await self._require_active_admin_in_tx(admin_uuid)
            group = await self._session.scalar(
                select(ORMGroup)
                .where(
                    ORMGroup.group_id == group_uuid,
                    ORMGroup.group_type.in_(_STUDY_GROUP_TYPES),
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if group is None:
                await self._session.rollback()
                return None
            member_count = int(
                await self._session.scalar(
                    select(func.count())
                    .select_from(ORMMembership)
                    .where(ORMMembership.group_id == group_uuid)
                )
                or 0
            )
            if max_members < member_count:
                raise AdministrationConflictError(
                    f"Maximum members cannot be below the current membership count of {member_count}."
                )
            group.group_name = name
            group.description = description
            group.group_type = GroupType(visibility.value)
            group.max_members = max_members
            group.last_updated_at = now
            self._session.add(
                ORMAuditEvent(
                    audit_event_id=uuid.uuid4(),
                    admin_id=admin_uuid,
                    action="update_group",
                    target_type="group",
                    target_id=str(group_uuid),
                    reason=reason,
                    event_timestamp=now,
                )
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        return await self.get_group(str(group_uuid))

    async def remove_group(
        self,
        *,
        group_id: str,
        actor: AdministrationActor,
    ) -> GovernanceActionResult | None:
        """Reversibly soft-remove a non-personal study group and audit atomically."""

        group_uuid = self._parse_uuid(group_id)
        if group_uuid is None:
            return None

        admin_uuid = self._require_valid_admin_uuid(actor.user_id)
        reason = self._require_valid_reason(actor.reason)

        try:
            await self._require_active_admin_in_tx(admin_uuid)

            grp = await self._session.scalar(
                select(ORMGroup)
                .where(
                    ORMGroup.group_id == group_uuid,
                    ORMGroup.group_type.in_(_STUDY_GROUP_TYPES),
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if grp is None:
                await self._session.rollback()
                return None

            if grp.deleted_at is not None:
                raise AdministrationConflictError(
                    "The study group is already removed."
                )

            now = datetime.now(timezone.utc)
            grp.deleted_at = now
            grp.last_updated_at = now

            self._session.add(
                ORMAuditEvent(
                    audit_event_id=uuid.uuid4(),
                    admin_id=admin_uuid,
                    action="remove_group",
                    target_type="group",
                    target_id=str(grp.group_id),
                    reason=reason,
                    event_timestamp=now,
                )
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        return GovernanceActionResult(
            resource_id=str(grp.group_id),
            status="removed",
            changed_at=now,
        )

    async def restore_group(
        self,
        *,
        group_id: str,
        actor: AdministrationActor,
    ) -> GovernanceActionResult | None:
        """Restore a soft-removed study group and audit atomically."""

        group_uuid = self._parse_uuid(group_id)
        if group_uuid is None:
            return None

        admin_uuid = self._require_valid_admin_uuid(actor.user_id)
        reason = self._require_valid_reason(actor.reason)

        try:
            await self._require_active_admin_in_tx(admin_uuid)

            grp = await self._session.scalar(
                select(ORMGroup)
                .where(
                    ORMGroup.group_id == group_uuid,
                    ORMGroup.group_type.in_(_STUDY_GROUP_TYPES),
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if grp is None:
                await self._session.rollback()
                return None

            if grp.deleted_at is None:
                raise AdministrationConflictError(
                    "The study group is already active."
                )

            now = datetime.now(timezone.utc)
            grp.deleted_at = None
            grp.last_updated_at = now

            self._session.add(
                ORMAuditEvent(
                    audit_event_id=uuid.uuid4(),
                    admin_id=admin_uuid,
                    action="restore_group",
                    target_type="group",
                    target_id=str(grp.group_id),
                    reason=reason,
                    event_timestamp=now,
                )
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        return GovernanceActionResult(
            resource_id=str(grp.group_id),
            status="active",
            changed_at=now,
        )

    # ------------------------------------------------------------------
    # Attachments
    # ------------------------------------------------------------------

    async def list_attachments(
        self,
        *,
        search: str | None,
        status: AdministrationAttachmentStatus | None,
        source: AdministrationAttachmentSource | None,
        include_removed: bool,
        cursor: str | None,
        limit: int,
    ) -> AdminAttachmentPage:
        """List attachments with source classification and safe metadata only."""

        self._validate_limit(limit)
        cursor_pos = (
            self._decode_int_cursor(cursor, kind="attachments")
            if cursor is not None
            else None
        )

        conditions = []
        if not include_removed:
            conditions.append(ORMAttachment.deleted_at.is_(None))
        if status is not None:
            conditions.append(
                ORMAttachment.processing_status
                == AttachmentStatus(status.value)
            )
        if source == AdministrationAttachmentSource.MY_NOTES:
            conditions.append(ORMAttachment.channel_id.is_(None))
        elif source == AdministrationAttachmentSource.PERSONAL_CHAT:
            conditions.append(ORMAttachment.channel_id.is_not(None))
            conditions.append(ORMGroup.group_type == GroupType.PERSONAL)
        elif source == AdministrationAttachmentSource.STUDY_GROUP:
            conditions.append(ORMAttachment.channel_id.is_not(None))
            conditions.append(ORMGroup.group_type.in_(_STUDY_GROUP_TYPES))

        if search:
            pattern = self._like_pattern(search)
            search_clauses = [
                ORMAttachment.title.ilike(pattern, escape="\\"),
                ORMAttachment.file_name.ilike(pattern, escape="\\"),
                ORMUser.fullname.ilike(pattern, escape="\\"),
                ORMUser.email.ilike(pattern, escape="\\"),
            ]
            if search.isdigit():
                search_clauses.append(
                    ORMAttachment.attachment_id == int(search)
                )
            conditions.append(or_(*search_clauses))

        if cursor_pos is not None:
            cursor_uploaded_at, cursor_attachment_id = cursor_pos
            conditions.append(
                or_(
                    ORMAttachment.uploaded_at < cursor_uploaded_at,
                    and_(
                        ORMAttachment.uploaded_at == cursor_uploaded_at,
                        ORMAttachment.attachment_id < cursor_attachment_id,
                    ),
                )
            )

        rows = list(
            (
                await self._session.execute(
                    select(ORMAttachment, ORMUser.fullname, ORMGroup.group_type)
                    .join(ORMUser, ORMUser.user_id == ORMAttachment.uploaded_by)
                    .outerjoin(
                        ORMChannel,
                        ORMChannel.channel_id == ORMAttachment.channel_id,
                    )
                    .outerjoin(
                        ORMGroup,
                        ORMGroup.group_id
                        == func.coalesce(
                            ORMAttachment.group_id, ORMChannel.group_id
                        ),
                    )
                    .where(*conditions)
                    .order_by(
                        ORMAttachment.uploaded_at.desc(),
                        ORMAttachment.attachment_id.desc(),
                    )
                    .limit(limit + 1)
                )
            ).all()
        )
        has_more = len(rows) > limit
        page_rows = rows[:limit]
        next_cursor = (
            self._encode_int_cursor(
                kind="attachments",
                timestamp=page_rows[-1][0].uploaded_at,
                entity_id=page_rows[-1][0].attachment_id,
            )
            if has_more and page_rows
            else None
        )

        items = tuple(
            self._to_attachment_summary(
                attachment=att,
                uploader_name=uploader_name,
                group_type=group_type,
            )
            for att, uploader_name, group_type in page_rows
        )
        return AdminAttachmentPage(items=items, next_cursor=next_cursor)

    async def get_attachment(
        self,
        attachment_id: int,
    ) -> AdminAttachmentDetails | None:
        """Return safe attachment processing details without exposing object_path."""

        if attachment_id <= 0:
            return None

        row = (
            await self._session.execute(
                select(ORMAttachment, ORMUser.fullname, ORMGroup.group_type)
                .join(ORMUser, ORMUser.user_id == ORMAttachment.uploaded_by)
                .outerjoin(
                    ORMChannel,
                    ORMChannel.channel_id == ORMAttachment.channel_id,
                )
                .outerjoin(
                    ORMGroup,
                    ORMGroup.group_id
                    == func.coalesce(
                        ORMAttachment.group_id, ORMChannel.group_id
                    ),
                )
                .where(ORMAttachment.attachment_id == attachment_id)
            )
        ).first()
        if row is None:
            return None

        att, uploader_name, group_type = row
        summary = self._to_attachment_summary(
            attachment=att,
            uploader_name=uploader_name,
            group_type=group_type,
        )

        duration_seconds: int | None = None
        if (
            att.processing_started_at is not None
            and att.processing_completed_at is not None
        ):
            duration_seconds = max(
                0,
                int(
                    (
                        att.processing_completed_at - att.processing_started_at
                    ).total_seconds()
                ),
            )

        return AdminAttachmentDetails(
            attachment=summary,
            uploader_user_id=str(att.uploaded_by),
            content_type=att.file_type,
            processing_progress=att.processing_progress,
            processing_started_at=att.processing_started_at,
            processing_completed_at=att.processing_completed_at,
            processing_duration_seconds=duration_seconds,
            safe_processing_error=self._sanitize_operational_message(
                att.processing_error
            ),
        )

    async def get_attachment_file(
        self,
        *,
        attachment_id: int,
        actor: AdministrationActor,
    ) -> AdminAttachmentFile | None:
        """Read a non-removed private PDF and record administrator access."""

        if attachment_id <= 0:
            return None
        admin_uuid = self._require_valid_admin_uuid(actor.user_id)
        reason = self._require_valid_reason(actor.reason)
        try:
            await self._require_active_admin_in_tx(admin_uuid)
            attachment = await self._session.scalar(
                select(ORMAttachment).where(
                    ORMAttachment.attachment_id == attachment_id,
                    ORMAttachment.deleted_at.is_(None),
                )
            )
            if attachment is None:
                await self._session.rollback()
                return None
            if self._attachment_storage is None:
                raise AdministrationConflictError("Private attachment storage is not configured.")
            try:
                content = await self._attachment_storage.read_pdf(attachment.object_path)
            except AttachmentStorageError as exc:
                raise AdministrationConflictError(
                    "The attachment file is temporarily unavailable."
                ) from exc
            now = datetime.now(timezone.utc)
            self._session.add(
                ORMAuditEvent(
                    audit_event_id=uuid.uuid4(),
                    admin_id=admin_uuid,
                    action="view_attachment",
                    target_type="attachment",
                    target_id=str(attachment.attachment_id),
                    reason=reason,
                    event_timestamp=now,
                )
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        return AdminAttachmentFile(
            attachment_id=attachment.attachment_id,
            filename=attachment.file_name,
            content_type=attachment.file_type or "application/pdf",
            content=content,
        )

    async def remove_attachment(
        self,
        *,
        attachment_id: int,
        actor: AdministrationActor,
    ) -> GovernanceActionResult | None:
        """Soft-remove metadata, coordinate processing/storage safely, and audit."""

        if attachment_id <= 0:
            return None

        admin_uuid = self._require_valid_admin_uuid(actor.user_id)
        reason = self._require_valid_reason(actor.reason)

        try:
            await self._require_active_admin_in_tx(admin_uuid)

            att = await self._session.scalar(
                select(ORMAttachment)
                .where(ORMAttachment.attachment_id == attachment_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if att is None:
                await self._session.rollback()
                return None

            if att.deleted_at is not None:
                raise AdministrationConflictError(
                    "The attachment is already removed."
                )

            now = datetime.now(timezone.utc)
            object_path = att.object_path
            await self._soft_remove_attachment_in_tx(att=att, now=now)

            self._session.add(
                ORMAuditEvent(
                    audit_event_id=uuid.uuid4(),
                    admin_id=admin_uuid,
                    action="remove_attachment",
                    target_type="attachment",
                    target_id=str(att.attachment_id),
                    reason=reason,
                    event_timestamp=now,
                )
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        # Cross-system coordination (PostgreSQL + Private Object Storage):
        # Metadata soft-deletion, derived chunk/graph soft-deletion, processing
        # termination, and the AuditEvent are committed atomically above so
        # in-flight workers (which filter deleted_at IS NULL) cannot re-publish
        # the file. Private PDF deletion is then executed idempotently below
        # (delete_pdf returns False if already deleted). A dedicated outbox
        # table/worker can additionally sweep pending storage deletions if the
        # process crashes after DB commit.
        await self._delete_private_pdf_idempotently(object_path)

        return GovernanceActionResult(
            resource_id=str(attachment_id),
            status="removed",
            changed_at=now,
        )

    async def retry_attachment(
        self,
        *,
        attachment_id: int,
        actor: AdministrationActor,
    ) -> GovernanceActionResult | None:
        """Lock failed non-removed attachment, reset state, audit, and enqueue once."""

        if attachment_id <= 0:
            return None

        admin_uuid = self._require_valid_admin_uuid(actor.user_id)
        reason = self._require_valid_reason(actor.reason)

        try:
            await self._require_active_admin_in_tx(admin_uuid)

            att = await self._session.scalar(
                select(ORMAttachment)
                .where(ORMAttachment.attachment_id == attachment_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if att is None:
                await self._session.rollback()
                return None

            if att.deleted_at is not None:
                raise AdministrationConflictError(
                    "A removed attachment cannot be retried."
                )
            if att.processing_status != AttachmentStatus.FAILED:
                raise AdministrationConflictError(
                    "Only failed attachments can be retried."
                )

            now = datetime.now(timezone.utc)
            object_path = att.object_path
            att.processing_status = AttachmentStatus.QUEUED
            att.processing_progress = 0
            att.processing_error = None
            att.processing_started_at = None
            att.processing_completed_at = None
            att.last_updated_at = now

            self._session.add(
                ORMAuditEvent(
                    audit_event_id=uuid.uuid4(),
                    admin_id=admin_uuid,
                    action="retry_attachment",
                    target_type="attachment",
                    target_id=str(att.attachment_id),
                    reason=reason,
                    event_timestamp=now,
                )
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        # Cross-system coordination (PostgreSQL + Celery Worker Queue):
        # Row-level FOR UPDATE + transition from FAILED -> QUEUED guarantees
        # concurrent retry requests cannot enqueue duplicate jobs. If broker
        # dispatch fails after commit, revert processing_status back to FAILED
        # so the attachment does not remain stuck in QUEUED and can be safely
        # retried later (or replaced by a transactional outbox relay).
        if self._processing_dispatcher is not None:
            try:
                await self._processing_dispatcher.dispatch(
                    attachment_id=attachment_id,
                    object_path=object_path,
                )
            except Exception as exc:
                await self._mark_retry_dispatch_failed(attachment_id)
                raise AdministrationConflictError(
                    "Attachment processing could not be enqueued; please retry."
                ) from exc

        return GovernanceActionResult(
            resource_id=str(attachment_id),
            status="queued",
            changed_at=now,
        )

    # ------------------------------------------------------------------
    # Immutable administrative audit events
    # ------------------------------------------------------------------

    async def list_audit_events(
        self,
        *,
        admin_id: str | None,
        action: str | None,
        target_type: str | None,
        target_id: str | None,
        occurred_from: datetime | None,
        occurred_to: datetime | None,
        cursor: str | None,
        limit: int,
    ) -> AdminAuditEventPage:
        """Query immutable governance events with stable keyset pagination."""

        self._validate_limit(limit)
        if occurred_from and occurred_to and occurred_from > occurred_to:
            raise AdministrationValidationError(
                "occurred_from must not be after occurred_to."
            )

        cursor_pos = (
            self._decode_uuid_cursor(cursor, kind="audit_events")
            if cursor is not None
            else None
        )

        conditions = []
        if admin_id is not None:
            parsed_admin = self._parse_uuid(admin_id)
            if parsed_admin is None:
                raise AdministrationValidationError(
                    "admin_id must be a valid UUID."
                )
            conditions.append(ORMAuditEvent.admin_id == parsed_admin)
        if action is not None:
            conditions.append(func.lower(ORMAuditEvent.action) == action.lower())
        if target_type is not None:
            conditions.append(
                func.lower(ORMAuditEvent.target_type) == target_type.lower()
            )
        if target_id is not None:
            conditions.append(ORMAuditEvent.target_id == target_id)

        if occurred_from is not None:
            conditions.append(ORMAuditEvent.event_timestamp >= occurred_from)
        if occurred_to is not None:
            conditions.append(ORMAuditEvent.event_timestamp <= occurred_to)

        if cursor_pos is not None:
            cursor_timestamp, cursor_event_id = cursor_pos
            conditions.append(
                or_(
                    ORMAuditEvent.event_timestamp < cursor_timestamp,
                    and_(
                        ORMAuditEvent.event_timestamp == cursor_timestamp,
                        ORMAuditEvent.audit_event_id < cursor_event_id,
                    ),
                )
            )

        rows = list(
            (
                await self._session.execute(
                    select(ORMAuditEvent, ORMUser.fullname)
                    .join(ORMUser, ORMUser.user_id == ORMAuditEvent.admin_id)
                    .where(*conditions)
                    .order_by(
                        ORMAuditEvent.event_timestamp.desc(),
                        ORMAuditEvent.audit_event_id.desc(),
                    )
                    .limit(limit + 1)
                )
            ).all()
        )
        has_more = len(rows) > limit
        page_rows = rows[:limit]
        next_cursor = (
            self._encode_uuid_cursor(
                kind="audit_events",
                timestamp=page_rows[-1][0].event_timestamp,
                entity_id=page_rows[-1][0].audit_event_id,
            )
            if has_more and page_rows
            else None
        )

        items = tuple(
            self._to_audit_event(audit, admin_name)
            for audit, admin_name in page_rows
        )
        return AdminAuditEventPage(items=items, next_cursor=next_cursor)

    async def get_audit_event(
        self, audit_event_id: str
    ) -> AdminAuditEvent | None:
        """Load one sanitized immutable governance event."""

        audit_uuid = self._parse_uuid(audit_event_id)
        if audit_uuid is None:
            return None

        row = (
            await self._session.execute(
                select(ORMAuditEvent, ORMUser.fullname)
                .join(ORMUser, ORMUser.user_id == ORMAuditEvent.admin_id)
                .where(ORMAuditEvent.audit_event_id == audit_uuid)
            )
        ).first()
        if row is None:
            return None
        return self._to_audit_event(row[0], row[1])

    # ------------------------------------------------------------------
    # Report Management
    # ------------------------------------------------------------------

    async def list_reports(
        self,
        *,
        search: str | None,
        status: ReportStatus | None,
        target_type: ReportTargetType | None,
        cursor: str | None,
        limit: int,
    ) -> AdminReportPage:
        """List user reports with search/status/target filters and cursor pagination."""

        self._validate_limit(limit)
        cursor_pos = (
            self._decode_uuid_cursor(cursor, kind="reports")
            if cursor is not None
            else None
        )

        conditions = []
        if status is not None:
            conditions.append(
                ORMUserReport.status == ORMReportStatus(status.value)
            )
        if target_type is not None:
            conditions.append(
                ORMUserReport.target_type
                == ORMReportTargetType(target_type.value)
            )
        if search:
            pattern = self._like_pattern(search)
            search_clauses = [
                ORMUserReport.description.ilike(pattern, escape="\\"),
                ORMUser.fullname.ilike(pattern, escape="\\"),
                ORMUser.email.ilike(pattern, escape="\\"),
            ]
            maybe_uuid = self._parse_uuid(search)
            if maybe_uuid is not None:
                search_clauses.append(ORMUserReport.report_id == maybe_uuid)
                search_clauses.append(
                    ORMUserReport.target_group_id == maybe_uuid
                )
            if search.isdigit():
                numeric_id = int(search)
                search_clauses.append(
                    ORMUserReport.target_message_id == numeric_id
                )
                search_clauses.append(
                    ORMUserReport.target_file_id == numeric_id
                )
            conditions.append(or_(*search_clauses))

        if cursor_pos is not None:
            cursor_created_at, cursor_report_id = cursor_pos
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
                    .join(
                        ORMUser,
                        ORMUser.user_id == ORMUserReport.reporter_user_id,
                    )
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
            self._encode_uuid_cursor(
                kind="reports",
                timestamp=page_rows[-1].created_at,
                entity_id=page_rows[-1].report_id,
            )
            if has_more and page_rows
            else None
        )

        return AdminReportPage(
            items=tuple(self._to_admin_report_summary(row) for row in page_rows),
            next_cursor=next_cursor,
        )

    async def get_report(self, report_id: str) -> AdminReportDetails | None:
        """Load one report's preserved snapshot, bounded context, evidence, and timeline."""

        report_uuid = self._parse_uuid(report_id)
        if report_uuid is None:
            return None

        row = (
            await self._session.execute(
                select(ORMUserReport, ORMUser.fullname)
                .join(
                    ORMUser, ORMUser.user_id == ORMUserReport.reporter_user_id
                )
                .where(ORMUserReport.report_id == report_uuid)
            )
        ).first()
        if row is None:
            return None

        report_row, reporter_name = row

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

        actor_alias = aliased(ORMUser)
        activity_rows = (
            await self._session.execute(
                select(
                    ORMReportActivityEvent,
                    actor_alias.fullname,
                    ORMReportNote.note,
                )
                .join(
                    actor_alias,
                    actor_alias.user_id == ORMReportActivityEvent.actor_id,
                )
                .outerjoin(
                    ORMReportNote,
                    ORMReportNote.note_id
                    == ORMReportActivityEvent.report_note_id,
                )
                .where(ORMReportActivityEvent.report_id == report_uuid)
                .order_by(
                    ORMReportActivityEvent.event_timestamp.asc(),
                    ORMReportActivityEvent.activity_event_id.asc(),
                )
            )
        ).all()

        activities = tuple(
            AdminReportActivity(
                activity_id=str(activity.activity_event_id),
                event_type=AdminReportActivityType(activity.action.value),
                summary=(
                    activity.summary
                    or note_text
                    or activity.action.value
                ),
                actor_id=str(activity.actor_id),
                actor_name=actor_name,
                actor_type=AdministrationUserRole(activity.actor_type.value),
                occurred_at=activity.event_timestamp,
            )
            for activity, actor_name, note_text in activity_rows
        )

        # Adapt database ``case_closed_at`` (populated for both resolved and
        # dismissed reports) to the stable API/domain field ``resolved_at``.
        return AdminReportDetails(
            report=self._to_admin_report_summary(report_row),
            reporter_user_id=str(report_row.reporter_user_id),
            reporter_name=reporter_name,
            description=report_row.description,
            target_snapshot=self._sanitize_target_snapshot(report_row),
            limited_context_snapshot=self._sanitize_limited_context_snapshot(
                report_row.limited_context_snapshot
            ),
            evidence=tuple(
                AdminReportEvidence(
                    evidence_id=str(ev.evidence_id),
                    filename=ev.file_name,
                    content_type=ev.file_type,
                )
                for ev in evidence_rows
            ),
            activity=activities,
            resolved_at=report_row.case_closed_at,
            resolution_outcome=(
                AdminReportResolutionOutcome(report_row.outcome.value)
                if report_row.outcome is not None
                else None
            ),
            internal_resolution_reason=report_row.internal_resolution_reason,
            public_summary=report_row.public_summary,
        )

    async def start_report_review(
        self,
        *,
        report_id: str,
        actor: AdministrationActor,
    ) -> AdminReportDetails | None:
        """Atomically transition ``submitted -> under_review`` and log activity."""

        report_uuid = self._parse_uuid(report_id)
        if report_uuid is None:
            return None

        admin_uuid = self._require_valid_admin_uuid(actor.user_id)
        reason = self._require_valid_reason(actor.reason)

        try:
            await self._require_active_admin_in_tx(admin_uuid)

            report = await self._lock_report_in_tx(report_uuid)
            if report is None:
                await self._session.rollback()
                return None

            if report.status != ORMReportStatus.SUBMITTED:
                raise AdministrationConflictError(
                    "Only a submitted report can enter review."
                )

            now = datetime.now(timezone.utc)
            report.status = ORMReportStatus.UNDER_REVIEW
            report.last_updated_at = now

            self._session.add(
                ORMReportActivityEvent(
                    activity_event_id=uuid.uuid4(),
                    report_id=report.report_id,
                    actor_type=ORMUserRole.ADMIN,
                    actor_id=admin_uuid,
                    action=ORMReportActivityAction.REVIEW_STARTED,
                    summary=reason,
                    event_timestamp=now,
                )
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        return await self.get_report(report_id)

    async def add_report_note(
        self,
        *,
        report_id: str,
        administrator_user_id: str,
        note: str,
    ) -> AdminReportDetails | None:
        """Append an immutable internal note while the report is ``under_review``."""

        report_uuid = self._parse_uuid(report_id)
        if report_uuid is None:
            return None

        admin_uuid = self._require_valid_admin_uuid(administrator_user_id)
        clean_note = note.strip()
        if len(clean_note) < 2:
            raise AdministrationValidationError(
                "An internal note must contain at least 2 characters."
            )

        try:
            await self._require_active_admin_in_tx(admin_uuid)

            report = await self._lock_report_in_tx(report_uuid)
            if report is None:
                await self._session.rollback()
                return None

            self._ensure_report_under_review(report)

            now = datetime.now(timezone.utc)
            note_uuid = uuid.uuid4()
            orm_note = ORMReportNote(
                note_id=note_uuid,
                report_id=report.report_id,
                admin_id=admin_uuid,
                note=clean_note,
                created_at=now,
            )
            self._session.add(orm_note)
            await self._session.flush()

            self._session.add(
                ORMReportActivityEvent(
                    activity_event_id=uuid.uuid4(),
                    report_id=report.report_id,
                    actor_type=ORMUserRole.ADMIN,
                    actor_id=admin_uuid,
                    action=ORMReportActivityAction.NOTE_ADDED,
                    report_note_id=note_uuid,
                    summary=clean_note,
                    event_timestamp=now,
                )
            )
            report.last_updated_at = now

            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        return await self.get_report(report_id)

    async def perform_report_governance_action(
        self,
        *,
        report_id: str,
        action: AdminReportGovernanceAction,
        actor: AdministrationActor,
    ) -> GovernanceActionResult | None:
        """Apply a target-specific governance mutation and record both audit and report activity."""

        report_uuid = self._parse_uuid(report_id)
        if report_uuid is None:
            return None

        admin_uuid = self._require_valid_admin_uuid(actor.user_id)
        reason = self._require_valid_reason(actor.reason)
        deleted_object_path: str | None = None

        try:
            await self._require_active_admin_in_tx(admin_uuid)

            report = await self._lock_report_in_tx(report_uuid)
            if report is None:
                await self._session.rollback()
                return None

            self._ensure_report_under_review(report)

            allowed_actions = _ALLOWED_GOVERNANCE_ACTIONS.get(
                report.target_type, frozenset()
            )
            if action not in allowed_actions:
                raise AdministrationValidationError(
                    "The governance action does not match the report target."
                )

            now = datetime.now(timezone.utc)
            audit_target_type: str
            resource_id: str
            result_status: str

            if action == AdminReportGovernanceAction.REMOVE_MESSAGE:
                if report.target_message_id is None:
                    raise AdministrationResourceNotFoundError(
                        "The reported message was not found."
                    )
                msg = await self._session.scalar(
                    select(ORMMessage)
                    .where(ORMMessage.message_id == report.target_message_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                if msg is None:
                    raise AdministrationResourceNotFoundError(
                        "The reported message was not found."
                    )
                if msg.deleted_at is not None:
                    raise AdministrationConflictError(
                        "The reported message is already removed."
                    )
                msg.deleted_at = now
                audit_target_type = "message"
                resource_id = str(msg.message_id)
                result_status = "removed"

            elif action == AdminReportGovernanceAction.DEACTIVATE_MESSAGE_AUTHOR:
                if report.target_message_id is None:
                    raise AdministrationResourceNotFoundError(
                        "The reported message was not found."
                    )
                msg = await self._session.scalar(
                    select(ORMMessage)
                    .where(ORMMessage.message_id == report.target_message_id)
                    .with_for_update(read=True)
                )
                if msg is None:
                    raise AdministrationResourceNotFoundError(
                        "The reported message was not found."
                    )
                deactivated = await self._lock_and_deactivate_user_in_tx(
                    target_uuid=msg.user_id,
                    acting_admin_uuid=admin_uuid,
                    now_override=now,
                )
                if deactivated is None:
                    raise AdministrationResourceNotFoundError(
                        "The message author was not found."
                    )
                author_user, _ = deactivated
                audit_target_type = "user"
                resource_id = str(author_user.user_id)
                result_status = "deactivated"

            elif action == AdminReportGovernanceAction.REMOVE_GROUP:
                if report.target_group_id is None:
                    raise AdministrationResourceNotFoundError(
                        "The reported study group was not found."
                    )
                grp = await self._session.scalar(
                    select(ORMGroup)
                    .where(
                        ORMGroup.group_id == report.target_group_id,
                        ORMGroup.group_type.in_(_STUDY_GROUP_TYPES),
                    )
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                if grp is None:
                    raise AdministrationResourceNotFoundError(
                        "The reported study group was not found."
                    )
                if grp.deleted_at is not None:
                    raise AdministrationConflictError(
                        "The study group is already removed."
                    )
                grp.deleted_at = now
                grp.last_updated_at = now
                audit_target_type = "group"
                resource_id = str(grp.group_id)
                result_status = "removed"

            elif action == AdminReportGovernanceAction.REMOVE_FILE:
                if report.target_file_id is None:
                    raise AdministrationResourceNotFoundError(
                        "The reported file was not found."
                    )
                att = await self._session.scalar(
                    select(ORMAttachment)
                    .where(ORMAttachment.attachment_id == report.target_file_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                if att is None:
                    raise AdministrationResourceNotFoundError(
                        "The reported file was not found."
                    )
                if att.deleted_at is not None:
                    raise AdministrationConflictError(
                        "The attachment is already removed."
                    )
                deleted_object_path = att.object_path
                await self._soft_remove_attachment_in_tx(att=att, now=now)
                audit_target_type = "attachment"
                resource_id = str(att.attachment_id)
                result_status = "removed"

            else:
                raise AdministrationValidationError(
                    "Unsupported report governance action."
                )

            audit_uuid = uuid.uuid4()
            self._session.add(
                ORMAuditEvent(
                    audit_event_id=audit_uuid,
                    admin_id=admin_uuid,
                    action=action.value,
                    target_type=audit_target_type,
                    target_id=resource_id,
                    reason=reason,
                    event_timestamp=now,
                )
            )
            await self._session.flush()

            self._session.add(
                ORMReportActivityEvent(
                    activity_event_id=uuid.uuid4(),
                    report_id=report.report_id,
                    actor_type=ORMUserRole.ADMIN,
                    actor_id=admin_uuid,
                    action=ORMReportActivityAction.GOVERNANCE_ACTION,
                    audit_event_id=audit_uuid,
                    summary=f"Applied '{action.value}': {reason}",
                    event_timestamp=now,
                )
            )
            report.last_updated_at = now

            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        if deleted_object_path is not None:
            await self._delete_private_pdf_idempotently(deleted_object_path)

        return GovernanceActionResult(
            resource_id=resource_id,
            status=result_status,
            changed_at=now,
        )

    async def resolve_report(
        self,
        *,
        report_id: str,
        administrator_user_id: str,
        outcome: AdminReportResolutionOutcome,
        internal_reason: str,
        public_summary: str,
    ) -> AdminReportDetails | None:
        """Lock report, validate outcome, close as ``resolved``, and log activity."""

        report_uuid = self._parse_uuid(report_id)
        if report_uuid is None:
            return None

        admin_uuid = self._require_valid_admin_uuid(administrator_user_id)
        clean_reason = self._require_valid_reason(internal_reason)
        clean_summary = self._require_valid_public_summary(public_summary)

        try:
            await self._require_active_admin_in_tx(admin_uuid)

            report = await self._lock_report_in_tx(report_uuid)
            if report is None:
                await self._session.rollback()
                return None

            self._ensure_report_under_review(report)

            allowed_outcomes = _ALLOWED_RESOLUTION_OUTCOMES.get(
                report.target_type, frozenset()
            )
            if outcome not in allowed_outcomes:
                raise AdministrationValidationError(
                    "The resolution outcome does not match the report target."
                )

            now = datetime.now(timezone.utc)
            report.status = ORMReportStatus.RESOLVED
            report.outcome = ORMReportOutcome(outcome.value)
            report.internal_resolution_reason = clean_reason
            report.public_summary = clean_summary
            report.last_updated_at = now
            report.case_closed_at = now

            self._session.add(
                ORMReportActivityEvent(
                    activity_event_id=uuid.uuid4(),
                    report_id=report.report_id,
                    actor_type=ORMUserRole.ADMIN,
                    actor_id=admin_uuid,
                    action=ORMReportActivityAction.RESOLVED,
                    summary=f"Resolved ({outcome.value}): {clean_summary}",
                    event_timestamp=now,
                )
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        return await self.get_report(report_id)

    async def dismiss_report(
        self,
        *,
        report_id: str,
        administrator_user_id: str,
        internal_reason: str,
        public_summary: str,
    ) -> AdminReportDetails | None:
        """Lock report, close as ``dismissed``, and append immutable activity."""

        report_uuid = self._parse_uuid(report_id)
        if report_uuid is None:
            return None

        admin_uuid = self._require_valid_admin_uuid(administrator_user_id)
        clean_reason = self._require_valid_reason(internal_reason)
        clean_summary = self._require_valid_public_summary(public_summary)

        try:
            await self._require_active_admin_in_tx(admin_uuid)

            report = await self._lock_report_in_tx(report_uuid)
            if report is None:
                await self._session.rollback()
                return None

            self._ensure_report_under_review(report)

            now = datetime.now(timezone.utc)
            report.status = ORMReportStatus.DISMISSED
            report.outcome = None
            report.internal_resolution_reason = clean_reason
            report.public_summary = clean_summary
            report.last_updated_at = now
            report.case_closed_at = now

            self._session.add(
                ORMReportActivityEvent(
                    activity_event_id=uuid.uuid4(),
                    report_id=report.report_id,
                    actor_type=ORMUserRole.ADMIN,
                    actor_id=admin_uuid,
                    action=ORMReportActivityAction.DISMISSED,
                    summary=f"Dismissed: {clean_summary}",
                    event_timestamp=now,
                )
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        return await self.get_report(report_id)

    async def get_report_evidence(
        self,
        *,
        report_id: str,
        evidence_id: str,
        administrator_user_id: str,
    ) -> AdminEvidenceFile | None:
        """Verify report-owned evidence and record an immutable ``evidence_viewed`` event."""

        report_uuid = self._parse_uuid(report_id)
        evidence_uuid = self._parse_uuid(evidence_id)
        if report_uuid is None or evidence_uuid is None:
            return None

        admin_uuid = self._require_valid_admin_uuid(administrator_user_id)

        try:
            await self._require_active_admin_in_tx(admin_uuid)

            evidence = await self._session.scalar(
                select(ORMEvidence)
                .join(
                    ORMUserReport,
                    ORMUserReport.report_id == ORMEvidence.report_id,
                )
                .where(
                    ORMEvidence.report_id == report_uuid,
                    ORMEvidence.evidence_id == evidence_uuid,
                )
            )
            if evidence is None:
                await self._session.rollback()
                return None

            if self._evidence_storage is None:
                raise AdministrationConflictError(
                    "Private evidence storage is not configured."
                )
            try:
                content = await self._evidence_storage.read_evidence(
                    evidence.private_storage_key
                )
            except EvidenceStorageError as exc:
                raise AdministrationConflictError(
                    "The report evidence is temporarily unavailable."
                ) from exc

            now = datetime.now(timezone.utc)
            audit_event = ORMAuditEvent(
                audit_event_id=uuid.uuid4(),
                admin_id=admin_uuid,
                action="report_evidence_viewed",
                target_type="evidence",
                target_id=str(evidence.evidence_id),
                reason="Evidence viewed during authorized report investigation.",
                event_timestamp=now,
            )
            self._session.add(audit_event)
            self._session.add(
                ORMReportActivityEvent(
                    activity_event_id=uuid.uuid4(),
                    report_id=report_uuid,
                    actor_type=ORMUserRole.ADMIN,
                    actor_id=admin_uuid,
                    action=ORMReportActivityAction.EVIDENCE_VIEWED,
                    evidence_id=evidence.evidence_id,
                    audit_event_id=audit_event.audit_event_id,
                    summary=f"Viewed evidence '{evidence.file_name}'.",
                    event_timestamp=now,
                )
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        return AdminEvidenceFile(
            evidence_id=str(evidence.evidence_id),
            filename=evidence.file_name,
            content_type=evidence.file_type,
            content=content,
        )

    # ------------------------------------------------------------------
    # Internal transactional & mapping helpers
    # ------------------------------------------------------------------

    async def _require_active_admin_in_tx(
        self,
        admin_uuid: uuid.UUID,
    ) -> ORMUser:
        admin = await self._session.scalar(
            select(ORMUser)
            .where(
                ORMUser.user_id == admin_uuid,
                ORMUser.deleted_at.is_(None),
                ORMUser.status == ActivityStatus.ACTIVE,
                ORMUser.user_role == ORMUserRole.ADMIN,
            )
            .with_for_update(read=True)
        )
        if admin is None:
            raise AdministrationConflictError(
                "Administrator account is inactive or unauthorized."
            )
        return admin

    async def _lock_and_deactivate_user_in_tx(
        self,
        *,
        target_uuid: uuid.UUID,
        acting_admin_uuid: uuid.UUID,
        now_override: datetime | None = None,
    ) -> tuple[ORMUser, datetime] | None:
        if acting_admin_uuid == target_uuid:
            raise AdministrationConflictError(
                "Administrators cannot deactivate their own account."
            )

        target = await self._session.scalar(
            select(ORMUser)
            .where(
                ORMUser.user_id == target_uuid,
                ORMUser.deleted_at.is_(None),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if target is None:
            return None

        if target.status == ActivityStatus.DEACTIVATED:
            raise AdministrationConflictError(
                "The account is already deactivated."
            )

        if target.user_role == ORMUserRole.ADMIN:
            active_admin_ids = list(
                (
                    await self._session.scalars(
                        select(ORMUser.user_id)
                        .where(
                            ORMUser.deleted_at.is_(None),
                            ORMUser.user_role == ORMUserRole.ADMIN,
                            ORMUser.status == ActivityStatus.ACTIVE,
                        )
                        .order_by(ORMUser.user_id)
                        .with_for_update()
                    )
                ).all()
            )
            if len(active_admin_ids) <= 1:
                raise AdministrationConflictError(
                    "The final active administrator cannot be deactivated."
                )

        now = now_override or datetime.now(timezone.utc)
        target.status = ActivityStatus.DEACTIVATED
        target.last_updated_at = now
        return target, now

    async def _soft_remove_attachment_in_tx(
        self,
        *,
        att: ORMAttachment,
        now: datetime,
    ) -> None:
        att.deleted_at = now
        att.last_updated_at = now
        if att.processing_status in (
            AttachmentStatus.QUEUED,
            AttachmentStatus.PROCESSING,
        ):
            att.processing_status = AttachmentStatus.FAILED
            att.processing_progress = 0
            att.processing_error = "Attachment removed by administrator."
            att.processing_completed_at = now

        await self._session.execute(
            update(ORMChunk)
            .where(
                ORMChunk.attachment_id == att.attachment_id,
                ORMChunk.deleted_at.is_(None),
            )
            .values(deleted_at=now)
        )

        graph_ids = list(
            (
                await self._session.scalars(
                    select(ORMKnowledgeGraph.graph_id).where(
                        ORMKnowledgeGraph.attachment_id == att.attachment_id
                    )
                )
            ).all()
        )
        if graph_ids:
            await self._session.execute(
                update(ORMKnowledgeEdge)
                .where(
                    ORMKnowledgeEdge.graph_id.in_(graph_ids),
                    ORMKnowledgeEdge.deleted_at.is_(None),
                )
                .values(deleted_at=now, last_updated_at=now)
            )
            await self._session.execute(
                update(ORMKnowledgeNode)
                .where(
                    ORMKnowledgeNode.graph_id.in_(graph_ids),
                    ORMKnowledgeNode.deleted_at.is_(None),
                )
                .values(deleted_at=now, last_updated_at=now)
            )
            await self._session.execute(
                update(ORMKnowledgeGraph)
                .where(
                    ORMKnowledgeGraph.graph_id.in_(graph_ids),
                    ORMKnowledgeGraph.deleted_at.is_(None),
                )
                .values(deleted_at=now, last_updated_at=now)
            )

    async def _delete_private_pdf_idempotently(self, object_path: str) -> None:
        if self._attachment_storage is None or not object_path:
            return
        try:
            await self._attachment_storage.delete_pdf(object_path)
        except AttachmentStorageError:
            logger.warning(
                "Private PDF cleanup deferred or path already invalid during administrative removal."
            )

    async def _mark_retry_dispatch_failed(self, attachment_id: int) -> None:
        failure_time = datetime.now(timezone.utc)
        try:
            att = await self._session.scalar(
                select(ORMAttachment)
                .where(
                    ORMAttachment.attachment_id == attachment_id,
                    ORMAttachment.deleted_at.is_(None),
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if att is not None and att.processing_status == AttachmentStatus.QUEUED:
                att.processing_status = AttachmentStatus.FAILED
                att.processing_progress = 0
                att.processing_error = (
                    "Document processing could not be started."
                )
                att.processing_completed_at = failure_time
                att.last_updated_at = failure_time
                await self._session.commit()
        except Exception:
            await self._session.rollback()

    async def _lock_report_in_tx(
        self,
        report_uuid: uuid.UUID,
    ) -> ORMUserReport | None:
        return await self._session.scalar(
            select(ORMUserReport)
            .where(ORMUserReport.report_id == report_uuid)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    @staticmethod
    def _ensure_report_under_review(report: ORMUserReport) -> None:
        if report.status in (
            ORMReportStatus.RESOLVED,
            ORMReportStatus.DISMISSED,
        ):
            raise AdministrationConflictError(
                "Completed reports are read-only."
            )
        if report.status != ORMReportStatus.UNDER_REVIEW:
            raise AdministrationConflictError(
                "This action is available only while the report is under review."
            )

    async def _load_group_member_counts(
        self,
        group_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, int]:
        if not group_ids:
            return {}
        rows = (
            await self._session.execute(
                select(ORMMembership.group_id, func.count())
                .where(ORMMembership.group_id.in_(group_ids))
                .group_by(ORMMembership.group_id)
            )
        ).all()
        return {group_id: int(count) for group_id, count in rows}

    async def _load_group_active_channel_counts(
        self,
        group_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, int]:
        if not group_ids:
            return {}
        rows = (
            await self._session.execute(
                select(ORMChannel.group_id, func.count())
                .where(
                    ORMChannel.group_id.in_(group_ids),
                    ORMChannel.deleted_at.is_(None),
                )
                .group_by(ORMChannel.group_id)
            )
        ).all()
        return {group_id: int(count) for group_id, count in rows}

    @staticmethod
    def _to_user_summary(user: ORMUser) -> AdminUserSummary:
        return AdminUserSummary(
            user_id=str(user.user_id),
            full_name=user.fullname,
            email=user.email,
            role=AdministrationUserRole(user.user_role.value),
            status=AdministrationUserStatus(user.status.value),
            created_at=user.created_at,
            last_active_at=None,
            email_verified=user.email_verified_at is not None,
        )

    @staticmethod
    def _to_group_summary(
        *,
        group: ORMGroup,
        owner_name: str,
        member_count: int,
        channel_count: int,
    ) -> AdminGroupSummary:
        return AdminGroupSummary(
            group_id=str(group.group_id),
            name=group.group_name,
            visibility=AdministrationGroupVisibility(group.group_type.value),
            owner_name=owner_name,
            member_count=member_count,
            channel_count=channel_count,
            status=(
                AdministrationGroupStatus.ACTIVE
                if group.deleted_at is None
                else AdministrationGroupStatus.REMOVED
            ),
            created_at=group.created_at,
        )

    @classmethod
    def _to_attachment_summary(
        cls,
        *,
        attachment: ORMAttachment,
        uploader_name: str,
        group_type: GroupType | None,
    ) -> AdminAttachmentSummary:
        return AdminAttachmentSummary(
            attachment_id=attachment.attachment_id,
            title=attachment.title,
            file_name=attachment.file_name,
            uploader_name=uploader_name,
            source=cls._derive_attachment_source(attachment, group_type),
            file_size_bytes=attachment.file_size_bytes,
            status=AdministrationAttachmentStatus(
                attachment.processing_status.value
            ),
            uploaded_at=attachment.uploaded_at,
            removed=attachment.deleted_at is not None,
        )

    @staticmethod
    def _derive_attachment_source(
        attachment: ORMAttachment,
        group_type: GroupType | None,
    ) -> AdministrationAttachmentSource:
        if attachment.channel_id is None:
            return AdministrationAttachmentSource.MY_NOTES
        if group_type == GroupType.PERSONAL:
            return AdministrationAttachmentSource.PERSONAL_CHAT
        if group_type in _STUDY_GROUP_TYPES:
            return AdministrationAttachmentSource.STUDY_GROUP
        return (
            AdministrationAttachmentSource.PERSONAL_CHAT
            if attachment.show_in_library
            else AdministrationAttachmentSource.STUDY_GROUP
        )

    @staticmethod
    def _to_audit_event(
        audit: ORMAuditEvent,
        admin_name: str | None,
    ) -> AdminAuditEvent:
        return AdminAuditEvent(
            audit_event_id=str(audit.audit_event_id),
            admin_id=str(audit.admin_id),
            admin_name=admin_name,
            action=audit.action,
            target_type=audit.target_type,
            target_id=audit.target_id,
            reason=audit.reason,
            event_timestamp=audit.event_timestamp,
        )

    @staticmethod
    def _to_admin_report_summary(row: ORMUserReport) -> AdminReportSummary:
        # Per agreed contract mapping: target_description maps from user_reports.description.
        return AdminReportSummary(
            report_id=str(row.report_id),
            created_at=row.created_at,
            category=ReportCategory(row.category.value),
            target_type=ReportTargetType(row.target_type.value),
            target_description=row.description,
            status=ReportStatus(row.status.value),
        )

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
    ) -> tuple[dict[str, object], ...]:
        if not isinstance(raw, list):
            return ()
        items: list[dict[str, object]] = []
        for entry in raw:
            if isinstance(entry, dict):
                items.append(
                    {
                        str(key): value
                        for key, value in entry.items()
                        if str(key) not in _FORBIDDEN_SNAPSHOT_KEYS
                    }
                )
        return tuple(items)

    @staticmethod
    def _sanitize_operational_message(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None

        # Strip multi-line Python tracebacks to their non-traceback summary.
        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        if not lines:
            return None
        if any(line.startswith("Traceback (most recent call last)") for line in lines):
            non_frame_lines = [
                line
                for line in lines
                if not line.startswith("Traceback (most recent call last)")
                and not line.startswith('File "')
            ]
            cleaned = non_frame_lines[-1] if non_frame_lines else "Processing failed."
        else:
            cleaned = " ".join(lines)

        cleaned = _CREDENTIAL_URI_RE.sub("[redacted-uri]", cleaned)
        cleaned = _BEARER_OR_JWT_RE.sub("[redacted-token]", cleaned)
        cleaned = _PASSWORD_HASH_RE.sub("[redacted-secret]", cleaned)
        cleaned = _WINDOWS_PATH_RE.sub("[redacted-path]", cleaned)
        cleaned = _POSIX_PATH_RE.sub("[redacted-path]", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned[:500] if cleaned else None

    @staticmethod
    def _validate_limit(limit: int) -> None:
        if limit < 1:
            raise AdministrationValidationError("limit must be at least 1.")

    @classmethod
    def _require_valid_admin_uuid(cls, user_id: str) -> uuid.UUID:
        parsed = cls._parse_uuid(user_id)
        if parsed is None:
            raise AdministrationValidationError(
                "Administrator user_id must be a valid UUID."
            )
        return parsed

    @staticmethod
    def _require_valid_reason(reason: str) -> str:
        cleaned = reason.strip()
        if len(cleaned) < 10:
            raise AdministrationValidationError(
                "An administrative reason must contain at least 10 characters."
            )
        return cleaned

    @staticmethod
    def _require_valid_public_summary(summary: str) -> str:
        cleaned = summary.strip()
        if len(cleaned) < 10:
            raise AdministrationValidationError(
                "A public resolution summary must contain at least 10 characters."
            )
        return cleaned

    @staticmethod
    def _like_pattern(search: str) -> str:
        escaped = (
            search.strip()
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        return f"%{escaped}%"

    @staticmethod
    def _encode_uuid_cursor(
        *,
        kind: str,
        timestamp: datetime,
        entity_id: uuid.UUID,
    ) -> str:
        payload = json.dumps(
            {
                "v": 1,
                "k": kind,
                "ts": timestamp.isoformat(),
                "id": str(entity_id),
            },
            separators=(",", ":"),
        ).encode("utf-8")
        return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")

    @classmethod
    def _decode_uuid_cursor(
        cls,
        cursor: str,
        *,
        kind: str,
    ) -> tuple[datetime, uuid.UUID]:
        payload = cls._decode_cursor_payload(cursor, kind=kind)
        raw_id = payload.get("id")
        if not isinstance(raw_id, str):
            raise AdministrationValidationError("Invalid pagination cursor.")
        parsed_uuid = cls._parse_uuid(raw_id)
        if parsed_uuid is None:
            raise AdministrationValidationError("Invalid pagination cursor.")
        return cls._parse_cursor_timestamp(payload), parsed_uuid

    @staticmethod
    def _encode_int_cursor(
        *,
        kind: str,
        timestamp: datetime,
        entity_id: int,
    ) -> str:
        payload = json.dumps(
            {
                "v": 1,
                "k": kind,
                "ts": timestamp.isoformat(),
                "id": entity_id,
            },
            separators=(",", ":"),
        ).encode("utf-8")
        return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")

    @classmethod
    def _decode_int_cursor(
        cls,
        cursor: str,
        *,
        kind: str,
    ) -> tuple[datetime, int]:
        payload = cls._decode_cursor_payload(cursor, kind=kind)
        raw_id = payload.get("id")
        if isinstance(raw_id, bool) or not isinstance(raw_id, int) or raw_id <= 0:
            raise AdministrationValidationError("Invalid pagination cursor.")
        return cls._parse_cursor_timestamp(payload), raw_id

    @staticmethod
    def _decode_cursor_payload(
        cursor: str,
        *,
        kind: str,
    ) -> dict[str, Any]:
        cleaned = cursor.strip()
        if not cleaned:
            raise AdministrationValidationError("Invalid pagination cursor.")
        padding = "=" * (-len(cleaned) % 4)
        try:
            decoded = base64.urlsafe_b64decode(cleaned + padding).decode("utf-8")
            payload = json.loads(decoded)
        except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AdministrationValidationError(
                "Invalid pagination cursor."
            ) from exc

        if (
            not isinstance(payload, dict)
            or payload.get("v") != 1
            or payload.get("k") != kind
        ):
            raise AdministrationValidationError("Invalid pagination cursor.")
        return payload

    @staticmethod
    def _parse_cursor_timestamp(payload: dict[str, Any]) -> datetime:
        raw_ts = payload.get("ts")
        if not isinstance(raw_ts, str):
            raise AdministrationValidationError("Invalid pagination cursor.")
        try:
            ts = datetime.fromisoformat(raw_ts)
        except ValueError as exc:
            raise AdministrationValidationError(
                "Invalid pagination cursor."
            ) from exc
        if ts.tzinfo is None:
            raise AdministrationValidationError("Invalid pagination cursor.")
        return ts

    @staticmethod
    def _parse_uuid(value: str) -> uuid.UUID | None:
        try:
            return uuid.UUID(str(value).strip())
        except (TypeError, ValueError, AttributeError):
            return None
