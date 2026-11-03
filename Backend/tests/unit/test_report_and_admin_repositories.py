"""Unit tests for PostgreSQLReportRepository and PostgreSQLAdministrationRepository."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import configure_mappers

from app.domains.administration.application.services import (
    AdministrationService,
)
from app.domains.administration.domain.exceptions import (
    AdministrationConflictError,
    AdministrationValidationError,
)
from app.domains.administration.domain.models import (
    AdminReportActivityType,
    AdminReportGovernanceAction,
    AdminReportResolutionOutcome,
    AdministrationActor,
    AdministrationAttachmentSource,
    AdministrationAttachmentStatus,
    AdministrationGroupStatus,
    AdministrationUserRole,
    AdministrationUserStatus,
)
from app.domains.administration.infrastructure.repository import (
    PostgreSQLAdministrationRepository,
)
from app.domains.notes.domain.processing import AttachmentProcessingDispatcher
from app.domains.notes.domain.storage import AttachmentStorage
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
from app.domains.reports.domain.storage import EvidenceStorage
from app.domains.reports.infrastructure.repository import (
    PostgreSQLReportRepository,
)
from app.models.orm_models import (
    ActivityStatus,
    Attachment as ORMAttachment,
    AttachmentStatus,
    AuditEvent as ORMAuditEvent,
    Channel as ORMChannel,
    Evidence as ORMEvidence,
    Group as ORMGroup,
    GroupType,
    MemberRole,
    Message as ORMMessage,
    ReportActivityAction as ORMReportActivityAction,
    ReportActivityEvent as ORMReportActivityEvent,
    ReportCategory as ORMReportCategory,
    ReportNote as ORMReportNote,
    ReportOutcome as ORMReportOutcome,
    ReportStatus as ORMReportStatus,
    ReportTargetType as ORMReportTargetType,
    User as ORMUser,
    UserReport as ORMUserReport,
    UserRole as ORMUserRole,
)

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 11, 3, 10, 0, 0, tzinfo=timezone.utc)
PNG_BYTES = b"\x89PNG\r\n\x1a\nvalid-png-proof"


class FakeResult:
    """Minimal SQLAlchemy result wrapper for queued session responses."""

    def __init__(self, rows: list[Any] | None = None) -> None:
        self._rows = list(rows or [])

    def first(self) -> Any:
        return self._rows[0] if self._rows else None

    def all(self) -> list[Any]:
        return list(self._rows)


class FakeAsyncSession:
    """Deterministic fake AsyncSession recording added ORM entities and commits."""

    def __init__(
        self,
        *,
        scalars_queue: list[Any] | None = None,
        execute_queue: list[list[Any]] | None = None,
        flush_error: Exception | None = None,
    ) -> None:
        self._scalars_queue = list(scalars_queue or [])
        self._execute_queue = list(execute_queue or [])
        self._flush_error = flush_error
        self.added: list[Any] = []
        self.executed_statements: list[Any] = []
        self.scalar_statements: list[Any] = []
        self.commits = 0
        self.rollbacks = 0
        self.flushes = 0

    def add(self, instance: Any) -> None:
        self.added.append(instance)

    async def flush(self) -> None:
        self.flushes += 1
        if self._flush_error is not None:
            raise self._flush_error

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    async def scalar(self, statement: Any) -> Any:
        self.scalar_statements.append(statement)
        if not self._scalars_queue:
            return None
        item = self._scalars_queue.pop(0)
        if isinstance(item, list):
            return item[0] if item else None
        return item

    async def scalars(self, statement: Any) -> FakeResult:
        self.scalar_statements.append(statement)
        if not self._scalars_queue:
            return FakeResult([])
        item = self._scalars_queue.pop(0)
        if isinstance(item, list):
            return FakeResult(item)
        return FakeResult([] if item is None else [item])

    async def execute(self, statement: Any) -> FakeResult:
        self.executed_statements.append(statement)
        sql_text = str(statement).lstrip().upper()
        if sql_text.startswith("UPDATE"):
            return FakeResult([])
        if not self._execute_queue:
            return FakeResult([])
        return FakeResult(self._execute_queue.pop(0))


class RecordingAttachmentStorage(AttachmentStorage):
    def __init__(self) -> None:
        self.deleted_paths: list[str] = []

    async def store_pdf(self, data: bytes) -> str:
        del data
        return "/private/notes/stored.pdf"

    async def read_pdf(self, object_path: str) -> bytes:
        del object_path
        return b"%PDF-1.4"

    async def delete_pdf(self, object_path: str) -> bool:
        self.deleted_paths.append(object_path)
        return True


class RecordingDispatcher(AttachmentProcessingDispatcher):
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.calls: list[tuple[int, str]] = []

    async def dispatch(self, *, attachment_id: int, object_path: str) -> None:
        self.calls.append((attachment_id, object_path))
        if self.should_fail:
            raise RuntimeError("Redis broker unreachable")


class RecordingEvidenceStorage(EvidenceStorage):
    def __init__(self) -> None:
        self.items: dict[str, bytes] = {}

    async def store_evidence(self, key: str, data: bytes) -> None:
        self.items[key] = data

    async def read_evidence(self, key: str) -> bytes:
        return self.items[key]

    async def delete_evidence(self, key: str) -> bool:
        return self.items.pop(key, None) is not None


def _make_user(
    *,
    role: ORMUserRole = ORMUserRole.STUDENT,
    status: ActivityStatus = ActivityStatus.ACTIVE,
    user_id: uuid.UUID | None = None,
    name: str = "Test User",
) -> ORMUser:
    uid = user_id or uuid.uuid4()
    return ORMUser(
        user_id=uid,
        email=f"{uid.hex[:8]}@example.com",
        fullname=name,
        password_hash="$2b$12$supersecrethashvalue000000000000000000000",
        user_role=role,
        status=status,
        show_online_status=True,
        created_at=NOW,
    )


def _make_group(
    *,
    owner_id: uuid.UUID,
    group_type: GroupType = GroupType.PUBLIC,
    deleted_at: datetime | None = None,
) -> ORMGroup:
    return ORMGroup(
        group_id=uuid.uuid4(),
        group_name="COMP3851A Study Group",
        group_type=group_type,
        description="Capstone group",
        created_by=owner_id,
        current_owner=owner_id,
        max_members=20,
        created_at=NOW,
        last_updated_at=NOW + timedelta(minutes=5),
        deleted_at=deleted_at,
    )


def _make_channel(*, group_id: uuid.UUID, creator_id: uuid.UUID) -> ORMChannel:
    return ORMChannel(
        channel_id=uuid.uuid4(),
        channel_name="general",
        group_id=group_id,
        created_by=creator_id,
        created_at=NOW,
    )


def _make_message(
    *,
    message_id: int,
    user_id: uuid.UUID,
    channel_id: uuid.UUID,
    text: str,
    offset_seconds: int = 0,
    deleted_at: datetime | None = None,
) -> ORMMessage:
    return ORMMessage(
        message_id=message_id,
        user_id=user_id,
        channel_id=channel_id,
        message_content=text,
        sent_at=NOW + timedelta(seconds=offset_seconds),
        deleted_at=deleted_at,
    )


def _make_attachment(
    *,
    attachment_id: int,
    uploaded_by: uuid.UUID,
    channel_id: uuid.UUID | None,
    group_id: uuid.UUID | None,
    status: AttachmentStatus = AttachmentStatus.READY,
    show_in_library: bool = False,
    deleted_at: datetime | None = None,
    processing_error: str | None = None,
) -> ORMAttachment:
    return ORMAttachment(
        attachment_id=attachment_id,
        uploaded_by=uploaded_by,
        channel_id=channel_id,
        group_id=group_id,
        title="Lecture Slides",
        file_name="slides.pdf",
        file_type="application/pdf",
        file_size_bytes=4096,
        object_path=f"/var/private/notes/{attachment_id}.pdf",
        processing_status=status,
        processing_progress=100 if status == AttachmentStatus.READY else 0,
        processing_error=processing_error,
        show_in_library=show_in_library,
        uploaded_at=NOW,
        processing_started_at=NOW,
        processing_completed_at=NOW + timedelta(seconds=12),
        deleted_at=deleted_at,
    )


# ---------------------------------------------------------------------------
# 1. ORM Mapper & Version 8.1 Index Checks
# ---------------------------------------------------------------------------


async def test_orm_mappers_and_v8_1_indexes_configure_cleanly() -> None:
    configure_mappers()

    report_index_names = {idx.name for idx in ORMUserReport.__table__.indexes}
    assert {
        "uq_user_reports_active_reporter_message",
        "uq_user_reports_active_reporter_group",
        "uq_user_reports_active_reporter_file",
        "ix_user_reports_reporter_created_id",
        "ix_user_reports_created_id",
    }.issubset(report_index_names)

    audit_index_names = {idx.name for idx in ORMAuditEvent.__table__.indexes}
    assert "ix_audit_events_timestamp_id" in audit_index_names

    # Verify Evidence -> ReportActivityEvent is 1-to-many so repeated evidence
    # views do not trigger 1-to-1 multiplicity conflicts.
    prop = ORMEvidence.__mapper__.relationships["report_activity_events"]
    assert prop.uselist is True


# ---------------------------------------------------------------------------
# 2. PostgreSQLReportRepository Tests
# ---------------------------------------------------------------------------


async def test_create_message_report_snapshots_target_and_bounded_context_atomically() -> None:
    reporter = _make_user(name="Reporter")
    author = _make_user(name="Author")
    group = _make_group(owner_id=author.user_id)
    channel = _make_channel(group_id=group.group_id, creator_id=author.user_id)

    before_older = _make_message(
        message_id=10,
        user_id=author.user_id,
        channel_id=channel.channel_id,
        text="Two before",
        offset_seconds=-20,
    )
    before_newer = _make_message(
        message_id=11,
        user_id=reporter.user_id,
        channel_id=channel.channel_id,
        text="One before",
        offset_seconds=-10,
    )
    target_msg = _make_message(
        message_id=12,
        user_id=author.user_id,
        channel_id=channel.channel_id,
        text="Server-authoritative harassing message",
        offset_seconds=0,
    )
    after_1 = _make_message(
        message_id=13,
        user_id=reporter.user_id,
        channel_id=channel.channel_id,
        text="One after",
        offset_seconds=10,
    )
    after_2 = _make_message(
        message_id=14,
        user_id=author.user_id,
        channel_id=channel.channel_id,
        text="Two after",
        offset_seconds=20,
    )

    session = FakeAsyncSession(
        scalars_queue=[
            reporter,  # active reporter lookup
            101,  # membership_id in group
            None,  # no duplicate active report
            [before_newer, before_older],  # DESC query returns newest-before first
            [after_1, after_2],  # ASC query returns oldest-after first
        ],
        execute_queue=[
            [(target_msg, channel, group)],
        ],
    )
    evidence_storage = RecordingEvidenceStorage()
    repo = PostgreSQLReportRepository(
        session,
        evidence_storage=evidence_storage,
    )
    service = ReportService(repo)

    report = await service.create_report(
        reporter_user_id=str(reporter.user_id),
        target_type=ReportTargetType.MESSAGE,
        target_id="12",
        category=ReportCategory.HARASSMENT_BULLYING,
        description="Targeted harassment in study group channel.",
        include_limited_context=True,
        evidence=[
            EvidenceUpload(
                filename="../../unsafe/proof.png",
                content_type="image/png",
                content=PNG_BYTES,
            )
        ],
    )

    assert session.commits == 1
    assert report.target_id == "12"
    assert report.target_snapshot == {
        "user_id": str(author.user_id),
        "message_text": "Server-authoritative harassing message",
        "sent_timestamp": target_msg.sent_at.isoformat(),
    }
    assert [m["message_id"] for m in report.limited_context_snapshot] == [
        10,
        11,
        13,
        14,
    ]
    assert len(report.evidence) == 1
    assert report.evidence[0].filename == "proof.png"
    assert not hasattr(report.evidence[0], "private_storage_key")

    # Verify UserReport, Evidence, and ReportActivityEvent(report_submitted) were added together.
    added_types = [type(obj) for obj in session.added]
    assert added_types == [
        ORMUserReport,
        ORMEvidence,
        ORMReportActivityEvent,
    ]
    persisted_evidence = session.added[1]
    assert persisted_evidence.private_storage_key.startswith("reports/")
    assert evidence_storage.items[persisted_evidence.private_storage_key] == PNG_BYTES
    persisted_activity = session.added[2]
    assert persisted_activity.action == ORMReportActivityAction.REPORT_SUBMITTED


async def test_create_file_report_uses_attachment_id_not_object_path() -> None:
    reporter = _make_user(name="Reporter")
    uploader = _make_user(name="Uploader")
    group = _make_group(owner_id=uploader.user_id, group_type=GroupType.PRIVATE)
    channel = _make_channel(
        group_id=group.group_id, creator_id=uploader.user_id
    )
    attachment = _make_attachment(
        attachment_id=55,
        uploaded_by=uploader.user_id,
        channel_id=channel.channel_id,
        group_id=group.group_id,
    )

    session = FakeAsyncSession(
        scalars_queue=[
            reporter,
            777,  # reporter is a member of the group
            None,  # no active duplicate
        ],
        execute_queue=[
            [(attachment, channel, group)],
        ],
    )
    repo = PostgreSQLReportRepository(session)

    created = await repo.create_report(
        reporter_user_id=str(reporter.user_id),
        target_type=ReportTargetType.FILE,
        target_id="55",
        category=ReportCategory.INAPPROPRIATE_CONTENT,
        description="Uploaded PDF violates study-group guidelines.",
        include_limited_context=True,
        evidence=[],
    )

    assert created.target_snapshot == {
        "user_id": str(uploader.user_id),
        "attachment_id": 55,
        "sent_timestamp": attachment.uploaded_at.isoformat(),
    }
    assert "file_path" not in created.target_snapshot
    assert "object_path" not in created.target_snapshot
    assert created.limited_context_snapshot == []


async def test_create_report_enforces_access_missing_and_duplicate_errors() -> None:
    reporter = _make_user()
    owner = _make_user()
    private_group = _make_group(
        owner_id=owner.user_id, group_type=GroupType.PRIVATE
    )

    # Non-member cannot report private group
    denied_session = FakeAsyncSession(
        scalars_queue=[reporter, private_group, None]
    )
    repo = PostgreSQLReportRepository(denied_session)
    with pytest.raises(ReportPermissionDeniedError):
        await repo.create_report(
            reporter_user_id=str(reporter.user_id),
            target_type=ReportTargetType.GROUP,
            target_id=str(private_group.group_id),
            category=ReportCategory.SPAM_SCAM,
            description="Private group spam description.",
            include_limited_context=False,
            evidence=[],
        )
    assert denied_session.rollbacks == 1

    # Missing target -> ReportNotFoundError
    missing_session = FakeAsyncSession(scalars_queue=[reporter, None])
    with pytest.raises(ReportNotFoundError):
        await PostgreSQLReportRepository(missing_session).create_report(
            reporter_user_id=str(reporter.user_id),
            target_type=ReportTargetType.GROUP,
            target_id=str(uuid.uuid4()),
            category=ReportCategory.SPAM_SCAM,
            description="Missing group target description.",
            include_limited_context=False,
            evidence=[],
        )

    # Concurrent partial-unique constraint violation -> DuplicateReportError
    public_group = _make_group(
        owner_id=owner.user_id, group_type=GroupType.PUBLIC
    )
    dup_integrity = IntegrityError(
        "INSERT INTO user_reports ...",
        {},
        Exception(
            'duplicate key value violates unique constraint "uq_user_reports_active_reporter_group"'
        ),
    )
    dup_session = FakeAsyncSession(
        scalars_queue=[reporter, public_group, None],
        flush_error=dup_integrity,
    )
    with pytest.raises(DuplicateReportError):
        await PostgreSQLReportRepository(dup_session).create_report(
            reporter_user_id=str(reporter.user_id),
            target_type=ReportTargetType.GROUP,
            target_id=str(public_group.group_id),
            category=ReportCategory.SPAM_SCAM,
            description="Concurrent duplicate active report.",
            include_limited_context=False,
            evidence=[],
        )
    assert dup_session.rollbacks == 1


async def test_report_cursor_pagination_and_submitter_scoping_strip_private_keys() -> None:
    reporter_id = uuid.uuid4()
    r1 = ORMUserReport(
        report_id=uuid.uuid4(),
        reporter_user_id=reporter_id,
        target_type=ORMReportTargetType.FILE,
        target_file_id=42,
        description="First report description",
        category=ORMReportCategory.OTHER,
        status=ORMReportStatus.SUBMITTED,
        target_snapshot={
            "user_id": str(uuid.uuid4()),
            "file_path": "/var/private/secret.pdf",
            "sent_timestamp": NOW.isoformat(),
        },
        limited_context_snapshot=[],
        created_at=NOW,
    )
    r2 = ORMUserReport(
        report_id=uuid.uuid4(),
        reporter_user_id=reporter_id,
        target_type=ORMReportTargetType.FILE,
        target_file_id=43,
        description="Second report description",
        category=ORMReportCategory.OTHER,
        status=ORMReportStatus.SUBMITTED,
        target_snapshot={
            "user_id": str(uuid.uuid4()),
            "attachment_id": 43,
            "sent_timestamp": (NOW - timedelta(minutes=1)).isoformat(),
        },
        limited_context_snapshot=[],
        created_at=NOW - timedelta(minutes=1),
    )

    session = FakeAsyncSession(scalars_queue=[[r1, r2], []])
    repo = PostgreSQLReportRepository(session)

    page = await repo.list_reports(
        reporter_user_id=str(reporter_id),
        status=None,
        cursor=None,
        limit=1,
    )
    assert len(page.items) == 1
    assert page.next_cursor is not None
    # Legacy file_path is stripped and replaced with attachment_id
    assert "file_path" not in page.items[0].target_snapshot
    assert page.items[0].target_snapshot["attachment_id"] == 42

    decoded_ts, decoded_id = repo._decode_cursor(page.next_cursor)
    assert decoded_ts == r1.created_at
    assert decoded_id == r1.report_id

    with pytest.raises(ValueError, match="Invalid pagination cursor"):
        await repo.list_reports(
            reporter_user_id=str(reporter_id),
            status=None,
            cursor="not-a-valid-cursor",
            limit=10,
        )


# ---------------------------------------------------------------------------
# 3. PostgreSQLAdministrationRepository Tests
# ---------------------------------------------------------------------------


async def test_operational_status_removed_and_dashboard_is_available() -> None:
    repo = PostgreSQLAdministrationRepository(FakeAsyncSession())
    assert not hasattr(repo, "get_system_status")
    dashboard = await repo.get_dashboard()
    assert dashboard.active_users == 0
    assert dashboard.recent_audit_events == ()


async def test_admin_user_protections_and_atomic_audit_events() -> None:
    admin_1 = _make_user(role=ORMUserRole.ADMIN, name="Admin One")
    admin_2 = _make_user(role=ORMUserRole.ADMIN, name="Admin Two")
    student = _make_user(role=ORMUserRole.STUDENT, name="Student One")

    # 1. Self-deactivation rejected at repository level too
    repo_self = PostgreSQLAdministrationRepository(FakeAsyncSession())
    with pytest.raises(AdministrationConflictError, match="own account"):
        await repo_self.deactivate_user(
            user_id=str(admin_1.user_id),
            actor=AdministrationActor(
                user_id=str(admin_1.user_id),
                reason="Attempting self deactivation",
            ),
        )

    # 2. Final active administrator rejected under FOR UPDATE lock
    final_admin_session = FakeAsyncSession(
        scalars_queue=[
            admin_1,  # acting admin active check
            admin_2,  # locked target admin
            [admin_2.user_id],  # only 1 active admin remains under lock!
        ]
    )
    repo_final = PostgreSQLAdministrationRepository(final_admin_session)
    with pytest.raises(AdministrationConflictError, match="final active"):
        await repo_final.deactivate_user(
            user_id=str(admin_2.user_id),
            actor=AdministrationActor(
                user_id=str(admin_1.user_id),
                reason="Attempting to deactivate last admin",
            ),
        )
    assert final_admin_session.rollbacks == 1
    assert final_admin_session.commits == 0

    # 3. Valid student deactivation commits status change + AuditEvent together
    ok_session = FakeAsyncSession(scalars_queue=[admin_1, student])
    repo_ok = PostgreSQLAdministrationRepository(ok_session)
    result = await repo_ok.deactivate_user(
        user_id=str(student.user_id),
        actor=AdministrationActor(
            user_id=str(admin_1.user_id),
            reason="Confirmed repeated policy violations",
        ),
    )
    assert result is not None
    assert result.resource_id == str(student.user_id)
    assert result.status == "deactivated"
    assert student.status == ActivityStatus.DEACTIVATED
    assert ok_session.commits == 1
    assert len(ok_session.added) == 1
    assert isinstance(ok_session.added[0], ORMAuditEvent)
    assert ok_session.added[0].action == "deactivate_user"
    assert ok_session.added[0].reason == "Confirmed repeated policy violations"

    # 4. get_user sets last_active_at=None and groups_joined_count includes owned groups
    details_session = FakeAsyncSession(scalars_queue=[student, 3, 5, 2])
    details = await PostgreSQLAdministrationRepository(details_session).get_user(
        str(student.user_id)
    )
    assert details is not None
    assert details.user.last_active_at is None
    assert details.notes_count == 3
    assert details.groups_joined_count == 5
    assert details.groups_owned_count == 2
    assert not hasattr(details.user, "password_hash")


async def test_attachment_sanitization_removal_and_retry_coordination() -> None:
    admin = _make_user(role=ORMUserRole.ADMIN)
    student = _make_user(role=ORMUserRole.STUDENT, name="Student Uploader")
    raw_error = (
        'Traceback (most recent call last):\n'
        '  File "/app/workers/parser.py", line 42, in run\n'
        "RuntimeError: Failed reading /var/private/notes/99.pdf via "
        "postgresql://spc:secretpass@db:5432/spc with Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig"
    )
    failed_att = _make_attachment(
        attachment_id=99,
        uploaded_by=student.user_id,
        channel_id=None,
        group_id=None,
        status=AttachmentStatus.FAILED,
        show_in_library=True,
        processing_error=raw_error,
    )

    # get_attachment redacts paths, URIs, tokens, and tracebacks, and omits object_path
    read_session = FakeAsyncSession(
        execute_queue=[[(failed_att, student.fullname, None)]]
    )
    details = await PostgreSQLAdministrationRepository(
        read_session
    ).get_attachment(99)
    assert details is not None
    assert details.attachment.source == AdministrationAttachmentSource.MY_NOTES
    assert details.processing_duration_seconds == 12
    assert details.safe_processing_error is not None
    assert "/var/private" not in details.safe_processing_error
    assert "secretpass" not in details.safe_processing_error
    assert "eyJhbGci" not in details.safe_processing_error
    assert "Traceback" not in details.safe_processing_error
    assert not hasattr(details, "object_path")

    # retry_attachment resets state, commits AuditEvent, and dispatches once
    dispatcher = RecordingDispatcher()
    retry_session = FakeAsyncSession(scalars_queue=[admin, failed_att])
    retry_repo = PostgreSQLAdministrationRepository(
        retry_session, processing_dispatcher=dispatcher
    )
    retry_result = await retry_repo.retry_attachment(
        attachment_id=99,
        actor=AdministrationActor(
            user_id=str(admin.user_id),
            reason="Transient worker failure resolved",
        ),
    )
    assert retry_result is not None
    assert retry_result.status == "queued"
    assert failed_att.processing_status == AttachmentStatus.QUEUED
    assert failed_att.processing_progress == 0
    assert failed_att.processing_error is None
    assert failed_att.processing_started_at is None
    assert failed_att.processing_completed_at is None
    assert dispatcher.calls == [(99, "/var/private/notes/99.pdf")]

    # Second concurrent retry is rejected because status is now QUEUED != FAILED
    second_retry_session = FakeAsyncSession(scalars_queue=[admin, failed_att])
    with pytest.raises(AdministrationConflictError, match="Only failed"):
        await PostgreSQLAdministrationRepository(
            second_retry_session, processing_dispatcher=dispatcher
        ).retry_attachment(
            attachment_id=99,
            actor=AdministrationActor(
                user_id=str(admin.user_id),
                reason="Duplicate concurrent retry attempt",
            ),
        )

    # remove_attachment soft-deletes metadata/chunks/graphs, terminates processing,
    # commits AuditEvent, and deletes private PDF idempotently
    storage = RecordingAttachmentStorage()
    remove_session = FakeAsyncSession(
        scalars_queue=[
            admin,
            failed_att,  # currently QUEUED
            [701],  # graph_ids to soft-delete
        ]
    )
    remove_repo = PostgreSQLAdministrationRepository(
        remove_session, attachment_storage=storage
    )
    rem_result = await remove_repo.remove_attachment(
        attachment_id=99,
        actor=AdministrationActor(
            user_id=str(admin.user_id),
            reason="Removing policy-violating attachment",
        ),
    )
    assert rem_result is not None
    assert rem_result.status == "removed"
    assert failed_att.deleted_at is not None
    assert failed_att.processing_status == AttachmentStatus.FAILED
    assert storage.deleted_paths == ["/var/private/notes/99.pdf"]
    assert isinstance(remove_session.added[0], ORMAuditEvent)


async def test_audit_events_use_dedicated_contract() -> None:
    admin_id = uuid.uuid4()
    audit_row = ORMAuditEvent(
        audit_event_id=uuid.uuid4(),
        admin_id=admin_id,
        action="remove_group",
        target_type="group",
        target_id=str(uuid.uuid4()),
        reason="Spam study group removed after review",
        event_timestamp=NOW,
    )
    session = FakeAsyncSession(
        execute_queue=[[(audit_row, "Admin User")], [(audit_row, "Admin User")]]
    )
    repo = PostgreSQLAdministrationRepository(session)

    page = await repo.list_audit_events(
        admin_id=None,
        action=None,
        target_type=None,
        target_id=None,
        occurred_from=NOW - timedelta(hours=1),
        occurred_to=NOW + timedelta(hours=1),
        cursor=None,
        limit=10,
    )
    assert len(page.items) == 1
    assert page.items[0].audit_event_id == str(audit_row.audit_event_id)
    assert page.items[0].admin_name == "Admin User"
    assert page.items[0].action == "remove_group"

    single = await repo.get_audit_event(str(audit_row.audit_event_id))
    assert single is not None
    assert single.audit_event_id == str(audit_row.audit_event_id)


async def test_admin_report_lifecycle_governance_actions_and_evidence_views() -> None:
    admin = _make_user(role=ORMUserRole.ADMIN, name="Moderator One")
    reporter = _make_user(role=ORMUserRole.STUDENT, name="Student Reporter")
    offender = _make_user(role=ORMUserRole.STUDENT, name="Offending Author")
    group = _make_group(owner_id=offender.user_id)
    channel = _make_channel(
        group_id=group.group_id, creator_id=offender.user_id
    )
    msg = _make_message(
        message_id=501,
        user_id=offender.user_id,
        channel_id=channel.channel_id,
        text="Abusive message content",
    )

    report_row = ORMUserReport(
        report_id=uuid.uuid4(),
        reporter_user_id=reporter.user_id,
        target_type=ORMReportTargetType.MESSAGE,
        target_message_id=msg.message_id,
        description="Student reported abusive message.",
        category=ORMReportCategory.HARASSMENT_BULLYING,
        status=ORMReportStatus.SUBMITTED,
        target_snapshot={
            "user_id": str(offender.user_id),
            "message_text": msg.message_content,
            "sent_timestamp": msg.sent_at.isoformat(),
        },
        limited_context_snapshot=[],
        created_at=NOW,
    )
    submitted_activity = ORMReportActivityEvent(
        activity_event_id=uuid.uuid4(),
        report_id=report_row.report_id,
        actor_type=ORMUserRole.STUDENT,
        actor_id=reporter.user_id,
        action=ORMReportActivityAction.REPORT_SUBMITTED,
        summary="Report submitted.",
        event_timestamp=NOW,
    )
    evidence_row = ORMEvidence(
        evidence_id=uuid.uuid4(),
        report_id=report_row.report_id,
        private_storage_key=f"private/reports/{report_row.report_id}/ev1",
        file_name="screenshot.png",
        file_type="image/png",
        file_size_bytes=len(PNG_BYTES),
        created_at=NOW,
    )

    # 1. start_report_review transitions submitted -> under_review and records activity (not AuditEvent)
    start_session = FakeAsyncSession(
        scalars_queue=[
            admin,  # _require_active_admin_in_tx
            report_row,  # _lock_report_in_tx
            [evidence_row],  # get_report evidence load
        ],
        execute_queue=[
            [(report_row, reporter.fullname)],  # get_report main row
            [
                (submitted_activity, reporter.fullname, None),
            ],  # get_report activities
        ],
    )
    repo = PostgreSQLAdministrationRepository(start_session)
    reviewed_details = await repo.start_report_review(
        report_id=str(report_row.report_id),
        actor=AdministrationActor(
            user_id=str(admin.user_id),
            reason="Starting moderation review",
        ),
    )
    assert reviewed_details is not None
    assert reviewed_details.report.status == ReportStatus.UNDER_REVIEW
    assert (
        reviewed_details.report.target_description
        == "Student reported abusive message."
    )
    assert reviewed_details.activity[0].actor_id == str(reporter.user_id)
    assert reviewed_details.activity[0].actor_name == reporter.fullname
    assert reviewed_details.activity[0].actor_type == AdministrationUserRole.STUDENT
    assert len(start_session.added) == 1
    assert isinstance(start_session.added[0], ORMReportActivityEvent)
    assert (
        start_session.added[0].action == ORMReportActivityAction.REVIEW_STARTED
    )

    # 2. perform_report_governance_action(REMOVE_MESSAGE) inserts BOTH AuditEvent
    # and linked ReportActivityEvent, and returns (str(message_id), "removed", ...)
    gov_session = FakeAsyncSession(
        scalars_queue=[admin, report_row, msg]
    )
    gov_result = await PostgreSQLAdministrationRepository(
        gov_session
    ).perform_report_governance_action(
        report_id=str(report_row.report_id),
        action=AdminReportGovernanceAction.REMOVE_MESSAGE,
        actor=AdministrationActor(
            user_id=str(admin.user_id),
            reason="Removing harassing message from study group",
        ),
    )
    assert gov_result is not None
    assert gov_result.resource_id == "501"
    assert gov_result.status == "removed"
    assert msg.deleted_at is not None
    assert [type(item) for item in gov_session.added] == [
        ORMAuditEvent,
        ORMReportActivityEvent,
    ]
    audit_ev, rep_act = gov_session.added
    assert rep_act.audit_event_id == audit_ev.audit_event_id
    assert audit_ev.target_id == "501"

    # 3. get_report_evidence records evidence_viewed on EVERY view and never exposes private_storage_key
    ev_session = FakeAsyncSession(
        scalars_queue=[admin, evidence_row, admin, evidence_row]
    )
    evidence_storage = RecordingEvidenceStorage()
    evidence_storage.items[evidence_row.private_storage_key] = PNG_BYTES
    ev_repo = PostgreSQLAdministrationRepository(
        ev_session,
        evidence_storage=evidence_storage,
    )
    ev_file_1 = await ev_repo.get_report_evidence(
        report_id=str(report_row.report_id),
        evidence_id=str(evidence_row.evidence_id),
        administrator_user_id=str(admin.user_id),
    )
    ev_file_2 = await ev_repo.get_report_evidence(
        report_id=str(report_row.report_id),
        evidence_id=str(evidence_row.evidence_id),
        administrator_user_id=str(admin.user_id),
    )
    assert ev_file_1 is not None and ev_file_2 is not None
    assert ev_file_1.filename == "screenshot.png"
    assert not hasattr(ev_file_1, "private_storage_key")
    assert ev_file_1.content == PNG_BYTES
    assert len(ev_session.added) == 4
    assert all(
        item.action == ORMReportActivityAction.EVIDENCE_VIEWED
        for item in ev_session.added
        if isinstance(item, ORMReportActivityEvent)
    )
    assert sum(isinstance(item, ORMAuditEvent) for item in ev_session.added) == 2

    # 4. resolve_report sets case_closed_at (mapped to resolved_at) and locks completed report read-only
    resolve_session = FakeAsyncSession(
        scalars_queue=[
            admin,
            report_row,
            [evidence_row],
        ],
        execute_queue=[
            [(report_row, reporter.fullname)],
            [],
        ],
    )
    resolved = await PostgreSQLAdministrationRepository(
        resolve_session
    ).resolve_report(
        report_id=str(report_row.report_id),
        administrator_user_id=str(admin.user_id),
        outcome=AdminReportResolutionOutcome.CONTENT_REMOVED,
        internal_reason="Confirmed harassment; message removed.",
        public_summary="The reported content was removed following review.",
    )
    assert resolved is not None
    assert resolved.report.status == ReportStatus.RESOLVED
    assert resolved.resolved_at is not None
    assert resolved.resolved_at == report_row.case_closed_at
    assert (
        resolved.resolution_outcome
        == AdminReportResolutionOutcome.CONTENT_REMOVED
    )

    # Completed report is strictly read-only for subsequent notes, actions, or dismissals
    closed_session = FakeAsyncSession(scalars_queue=[admin, report_row])
    with pytest.raises(AdministrationConflictError, match="read-only"):
        await PostgreSQLAdministrationRepository(closed_session).dismiss_report(
            report_id=str(report_row.report_id),
            administrator_user_id=str(admin.user_id),
            internal_reason="Conflicting second decision attempt",
            public_summary="Attempting to overwrite resolved report.",
        )


async def test_group_governance_and_retry_dispatch_fallback() -> None:
    admin_1 = _make_user(role=ORMUserRole.ADMIN, name="Admin One")
    owner = _make_user(role=ORMUserRole.STUDENT, name="Group Owner")
    group = _make_group(owner_id=owner.user_id, group_type=GroupType.PUBLIC)
    ch = _make_channel(group_id=group.group_id, creator_id=owner.user_id)

    # get_group returns governance metadata, role breakdown, and channel names only
    get_session = FakeAsyncSession(
        scalars_queue=[[ch]],
        execute_queue=[
            [(group, owner.fullname, owner.fullname)],
            [(MemberRole.OWNER, 1), (MemberRole.ADMIN, 2), (MemberRole.MEMBER, 5)],
        ],
    )
    details = await PostgreSQLAdministrationRepository(get_session).get_group(
        str(group.group_id)
    )
    assert details is not None
    assert details.group.member_count == 8
    assert details.owner_count == 1
    assert details.admin_count == 2
    assert details.ordinary_member_count == 5
    assert len(details.channels) == 1
    assert details.channels[0].name == "general"

    # remove_group -> soft removal + AuditEvent
    rem_session = FakeAsyncSession(scalars_queue=[admin_1, group])
    rem_res = await PostgreSQLAdministrationRepository(rem_session).remove_group(
        group_id=str(group.group_id),
        actor=AdministrationActor(
            user_id=str(admin_1.user_id),
            reason="Removing study group after policy breach",
        ),
    )
    assert rem_res is not None
    assert rem_res.status == "removed"
    assert group.deleted_at is not None
    assert isinstance(rem_session.added[0], ORMAuditEvent)

    # restore_group -> reversible restore + AuditEvent
    res_session = FakeAsyncSession(scalars_queue=[admin_1, group])
    res_res = await PostgreSQLAdministrationRepository(res_session).restore_group(
        group_id=str(group.group_id),
        actor=AdministrationActor(
            user_id=str(admin_1.user_id),
            reason="Appeal approved; restoring study group",
        ),
    )
    assert res_res is not None
    assert res_res.status == "active"
    assert group.deleted_at is None
    assert isinstance(res_session.added[0], ORMAuditEvent)

    # retry_attachment reverts QUEUED -> FAILED cleanly if Celery broker dispatch fails
    failed_att = _make_attachment(
        attachment_id=105,
        uploaded_by=owner.user_id,
        channel_id=None,
        group_id=None,
        status=AttachmentStatus.FAILED,
        show_in_library=True,
    )
    broken_dispatcher = RecordingDispatcher(should_fail=True)
    fallback_session = FakeAsyncSession(
        scalars_queue=[admin_1, failed_att, failed_att]
    )
    with pytest.raises(AdministrationConflictError, match="could not be enqueued"):
        await PostgreSQLAdministrationRepository(
            fallback_session, processing_dispatcher=broken_dispatcher
        ).retry_attachment(
            attachment_id=105,
            actor=AdministrationActor(
                user_id=str(admin_1.user_id),
                reason="Retrying failed note while broker is down",
            ),
        )
    assert failed_att.processing_status == AttachmentStatus.FAILED
    assert failed_att.processing_error == "Document processing could not be started."


async def test_remaining_report_actions_notes_and_dismissal() -> None:
    admin_1 = _make_user(role=ORMUserRole.ADMIN, name="Admin One")
    admin_2 = _make_user(role=ORMUserRole.ADMIN, name="Admin Two")
    reporter = _make_user(role=ORMUserRole.STUDENT, name="Student Reporter")

    # DEACTIVATE_MESSAGE_AUTHOR enforces final-admin protection under lock
    admin_msg = _make_message(
        message_id=888,
        user_id=admin_2.user_id,
        channel_id=uuid.uuid4(),
        text="Admin authored message",
    )
    msg_report = ORMUserReport(
        report_id=uuid.uuid4(),
        reporter_user_id=reporter.user_id,
        target_type=ORMReportTargetType.MESSAGE,
        target_message_id=admin_msg.message_id,
        description="Reporting message by another admin",
        category=ORMReportCategory.OTHER,
        status=ORMReportStatus.UNDER_REVIEW,
        target_snapshot={},
        limited_context_snapshot=[],
        created_at=NOW,
    )
    last_admin_session = FakeAsyncSession(
        scalars_queue=[
            admin_1,
            msg_report,
            admin_msg,
            admin_2,
            [admin_2.user_id],  # only 1 active admin under lock
        ]
    )
    with pytest.raises(AdministrationConflictError, match="final active"):
        await PostgreSQLAdministrationRepository(
            last_admin_session
        ).perform_report_governance_action(
            report_id=str(msg_report.report_id),
            action=AdminReportGovernanceAction.DEACTIVATE_MESSAGE_AUTHOR,
            actor=AdministrationActor(
                user_id=str(admin_1.user_id),
                reason="Attempting to deactivate last active admin",
            ),
        )

    # REMOVE_FILE via report governance action deletes private PDF and returns (file_id, "removed")
    file_att = _make_attachment(
        attachment_id=321,
        uploaded_by=reporter.user_id,
        channel_id=uuid.uuid4(),
        group_id=uuid.uuid4(),
    )
    file_report = ORMUserReport(
        report_id=uuid.uuid4(),
        reporter_user_id=reporter.user_id,
        target_type=ORMReportTargetType.FILE,
        target_file_id=file_att.attachment_id,
        description="Reported group PDF file",
        category=ORMReportCategory.INAPPROPRIATE_CONTENT,
        status=ORMReportStatus.UNDER_REVIEW,
        target_snapshot={"attachment_id": 321},
        limited_context_snapshot=[],
        created_at=NOW,
    )
    storage = RecordingAttachmentStorage()
    file_gov_session = FakeAsyncSession(
        scalars_queue=[admin_1, file_report, file_att, []]
    )
    file_gov_res = await PostgreSQLAdministrationRepository(
        file_gov_session, attachment_storage=storage
    ).perform_report_governance_action(
        report_id=str(file_report.report_id),
        action=AdminReportGovernanceAction.REMOVE_FILE,
        actor=AdministrationActor(
            user_id=str(admin_1.user_id),
            reason="Removing inappropriate group attachment",
        ),
    )
    assert file_gov_res is not None
    assert file_gov_res.resource_id == "321"
    assert file_gov_res.status == "removed"
    assert storage.deleted_paths == ["/var/private/notes/321.pdf"]

    # add_report_note + dismiss_report sets outcome=None and maps case_closed_at -> resolved_at
    note_session = FakeAsyncSession(
        scalars_queue=[admin_1, file_report, []],
        execute_queue=[
            [(file_report, reporter.fullname)],
            [],
        ],
    )
    after_note = await PostgreSQLAdministrationRepository(
        note_session
    ).add_report_note(
        report_id=str(file_report.report_id),
        administrator_user_id=str(admin_1.user_id),
        note="Checked context and verified reporter claim.",
    )
    assert after_note is not None
    assert [type(x) for x in note_session.added] == [
        ORMReportNote,
        ORMReportActivityEvent,
    ]
    assert note_session.added[1].report_note_id == note_session.added[0].note_id

    dismiss_session = FakeAsyncSession(
        scalars_queue=[admin_1, file_report, []],
        execute_queue=[
            [(file_report, reporter.fullname)],
            [],
        ],
    )
    dismissed = await PostgreSQLAdministrationRepository(
        dismiss_session
    ).dismiss_report(
        report_id=str(file_report.report_id),
        administrator_user_id=str(admin_1.user_id),
        internal_reason="No violation found after reviewing evidence.",
        public_summary="The report was reviewed and dismissed.",
    )
    assert dismissed is not None
    assert dismissed.report.status == ReportStatus.DISMISSED
    assert dismissed.resolution_outcome is None
    assert dismissed.resolved_at is not None
    assert dismissed.resolved_at == file_report.case_closed_at


async def test_postgresql_sql_compilation_and_pydantic_schema_contracts() -> None:
    """Compile every repository SQL statement under PostgreSQL dialect and validate API schemas."""

    from sqlalchemy.dialects import postgresql

    from app.domains.administration.presentation.schemas import (
        AdminAttachmentDetailsResponse,
        AdminAttachmentPageResponse,
        AdminAuditEventPageResponse,
        AdminGroupDetailsResponse,
        AdminGroupPageResponse,
        AdminReportDetailsResponse,
        AdminReportPageResponse,
        AdminUserDetailsResponse,
        AdminUserPageResponse,
        GovernanceActionResponse,
    )
    from app.domains.reports.presentation.schemas import (
        ReportListResponse,
        ReportResponse,
    )

    pg_dialect = postgresql.dialect()

    def assert_all_compile(session: FakeAsyncSession) -> None:
        for stmt in (*session.scalar_statements, *session.executed_statements):
            compiled = str(
                stmt.compile(
                    dialect=pg_dialect,
                    compile_kwargs={"render_postcompile": True},
                )
            )
            assert compiled

    admin_1 = _make_user(role=ORMUserRole.ADMIN, name="Admin One")
    admin_2 = _make_user(role=ORMUserRole.ADMIN, name="Admin Two")
    student = _make_user(role=ORMUserRole.STUDENT, name="Student One")
    pub_group = _make_group(owner_id=student.user_id, group_type=GroupType.PUBLIC)
    ch = _make_channel(group_id=pub_group.group_id, creator_id=student.user_id)
    msg = _make_message(
        message_id=77,
        user_id=student.user_id,
        channel_id=ch.channel_id,
        text="Reported text",
    )
    att = _make_attachment(
        attachment_id=88,
        uploaded_by=student.user_id,
        channel_id=ch.channel_id,
        group_id=pub_group.group_id,
    )

    # 1. Compile all ReportRepository queries (message, group, file, list, get)
    rep_msg_session = FakeAsyncSession(
        scalars_queue=[student, 1, None],
        execute_queue=[[(msg, ch, pub_group)]],
    )
    rep_msg = await PostgreSQLReportRepository(rep_msg_session).create_report(
        reporter_user_id=str(student.user_id),
        target_type=ReportTargetType.MESSAGE,
        target_id="77",
        category=ReportCategory.SPAM_SCAM,
        description="Spam message without context window.",
        include_limited_context=False,
        evidence=[],
    )
    assert rep_msg.limited_context_snapshot == []
    assert_all_compile(rep_msg_session)
    ReportResponse.model_validate(rep_msg)

    rep_grp_session = FakeAsyncSession(scalars_queue=[student, pub_group, None])
    rep_grp = await PostgreSQLReportRepository(rep_grp_session).create_report(
        reporter_user_id=str(student.user_id),
        target_type=ReportTargetType.GROUP,
        target_id=str(pub_group.group_id),
        category=ReportCategory.SPAM_SCAM,
        description="Public group reportable by any active user.",
        include_limited_context=False,
        evidence=[],
    )
    assert rep_grp.target_snapshot["group_name"] == pub_group.group_name
    assert_all_compile(rep_grp_session)

    rep_file_session = FakeAsyncSession(
        scalars_queue=[student, 1, None],
        execute_queue=[[(att, ch, pub_group)]],
    )
    rep_file = await PostgreSQLReportRepository(rep_file_session).create_report(
        reporter_user_id=str(student.user_id),
        target_type=ReportTargetType.FILE,
        target_id="88",
        category=ReportCategory.INAPPROPRIATE_CONTENT,
        description="Study group attachment report check.",
        include_limited_context=False,
        evidence=[],
    )
    assert_all_compile(rep_file_session)

    persisted_report = rep_msg_session.added[0]
    list_rep_session = FakeAsyncSession(
        scalars_queue=[[persisted_report], [], persisted_report, []]
    )
    rep_repo = PostgreSQLReportRepository(list_rep_session)
    rep_page = await rep_repo.list_reports(
        reporter_user_id=str(student.user_id),
        status=ReportStatus.SUBMITTED,
        cursor=rep_repo._encode_cursor(NOW + timedelta(minutes=1), uuid.uuid4()),
        limit=10,
    )
    fetched_rep = await rep_repo.get_report(
        reporter_user_id=str(student.user_id),
        report_id=str(persisted_report.report_id),
    )
    assert fetched_rep is not None
    assert_all_compile(list_rep_session)
    ReportListResponse(
        items=[ReportResponse.model_validate(i) for i in rep_page.items],
        next_cursor=rep_page.next_cursor,
    )

    # 2. Compile AdministrationRepository list/detail/cursor queries & validate Pydantic schemas
    admin_list_session = FakeAsyncSession(
        scalars_queue=[
            [admin_1, student],  # list_users
            2,  # count_active_administrators
            [persisted_report],  # list_reports
        ],
        execute_queue=[
            [(pub_group, student.fullname)],  # list_groups
            [(pub_group.group_id, 4)],  # member counts
            [(pub_group.group_id, 2)],  # channel counts
            [(att, student.fullname, GroupType.PUBLIC)],  # list_attachments
        ],
    )
    admin_repo = PostgreSQLAdministrationRepository(admin_list_session)

    users_cursor = admin_repo._encode_uuid_cursor(
        kind="users", timestamp=NOW + timedelta(hours=1), entity_id=uuid.uuid4()
    )
    user_page = await admin_repo.list_users(
        search="100%_test",
        status=AdministrationUserStatus.ACTIVE,
        role=AdministrationUserRole.STUDENT,
        cursor=users_cursor,
        limit=1,
    )
    AdminUserPageResponse.model_validate(user_page)
    assert user_page.next_cursor is not None

    # Cross-kind cursor must be rejected
    with pytest.raises(AdministrationValidationError, match="Invalid pagination cursor"):
        await admin_repo.list_reports(
            search=None,
            status=None,
            target_type=None,
            cursor=users_cursor,
            limit=10,
        )

    assert await admin_repo.count_active_administrators() == 2

    groups_cursor = admin_repo._encode_uuid_cursor(
        kind="groups", timestamp=NOW + timedelta(hours=1), entity_id=uuid.uuid4()
    )
    group_page = await admin_repo.list_groups(
        search="COMP3851A",
        visibility=None,
        status=AdministrationGroupStatus.ACTIVE,
        cursor=groups_cursor,
        limit=10,
    )
    AdminGroupPageResponse.model_validate(group_page)

    att_cursor = admin_repo._encode_int_cursor(
        kind="attachments", timestamp=NOW + timedelta(hours=1), entity_id=999
    )
    att_page = await admin_repo.list_attachments(
        search="88",
        status=AdministrationAttachmentStatus.READY,
        source=AdministrationAttachmentSource.STUDY_GROUP,
        include_removed=False,
        cursor=att_cursor,
        limit=10,
    )
    AdminAttachmentPageResponse.model_validate(att_page)

    rep_cursor = admin_repo._encode_uuid_cursor(
        kind="reports", timestamp=NOW + timedelta(hours=1), entity_id=uuid.uuid4()
    )
    admin_rep_page = await admin_repo.list_reports(
        search="77",
        status=ReportStatus.SUBMITTED,
        target_type=ReportTargetType.MESSAGE,
        cursor=rep_cursor,
        limit=10,
    )
    AdminReportPageResponse.model_validate(admin_rep_page)

    assert_all_compile(admin_list_session)

    # Validate remaining response models
    u_det = await PostgreSQLAdministrationRepository(
        FakeAsyncSession(scalars_queue=[student, 1, 2, 1])
    ).get_user(str(student.user_id))
    AdminUserDetailsResponse.model_validate(u_det)

    g_det = await PostgreSQLAdministrationRepository(
        FakeAsyncSession(
            scalars_queue=[[ch]],
            execute_queue=[
                [(pub_group, student.fullname, student.fullname)],
                [(MemberRole.OWNER, 1)],
            ],
        )
    ).get_group(str(pub_group.group_id))
    AdminGroupDetailsResponse.model_validate(g_det)

    a_det = await PostgreSQLAdministrationRepository(
        FakeAsyncSession(
            execute_queue=[[(att, student.fullname, GroupType.PUBLIC)]]
        )
    ).get_attachment(88)
    AdminAttachmentDetailsResponse.model_validate(a_det)

    audit_page = await PostgreSQLAdministrationRepository(
        FakeAsyncSession(
            execute_queue=[
                [
                    (
                        ORMAuditEvent(
                            audit_event_id=uuid.uuid4(),
                            admin_id=admin_1.user_id,
                            action="reactivate_user",
                            target_type="user",
                            target_id=str(student.user_id),
                            reason="Restored student account",
                            event_timestamp=NOW,
                        ),
                        admin_1.fullname,
                    )
                ]
            ]
        )
    ).list_audit_events(
        admin_id=None,
        action=None,
        target_type=None,
        target_id=None,
        occurred_from=None,
        occurred_to=None,
        cursor=None,
        limit=10,
    )
    AdminAuditEventPageResponse.model_validate(audit_page)

    deactivated_student = _make_user(
        role=ORMUserRole.STUDENT, status=ActivityStatus.DEACTIVATED
    )
    react_session = FakeAsyncSession(
        scalars_queue=[admin_2, deactivated_student]
    )
    react_res = await PostgreSQLAdministrationRepository(
        react_session
    ).reactivate_user(
        user_id=str(deactivated_student.user_id),
        actor=AdministrationActor(
            user_id=str(admin_2.user_id),
            reason="Account reactivation approved",
        ),
    )
    GovernanceActionResponse.model_validate(react_res)
    assert_all_compile(react_session)

    rep_det = await PostgreSQLAdministrationRepository(
        FakeAsyncSession(
            scalars_queue=[[]],
            execute_queue=[
                [(persisted_report, student.fullname)],
                [],
            ],
        )
    ).get_report(str(persisted_report.report_id))
    AdminReportDetailsResponse.model_validate(rep_det)
