"""PostgreSQL integration tests for ReportRepository and AdministrationRepository."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domains.administration.domain.exceptions import (
    AdministrationConflictError,
)
from app.domains.administration.domain.models import (
    AdminReportGovernanceAction,
    AdminReportResolutionOutcome,
    AdministrationActor,
)
from app.domains.administration.infrastructure.repository import (
    PostgreSQLAdministrationRepository,
)
from app.domains.reports.domain.exceptions import (
    DuplicateReportError,
    ReportPermissionDeniedError,
)
from app.domains.reports.domain.models import (
    EvidenceUpload,
    ReportCategory,
    ReportStatus,
    ReportTargetType,
)
from app.domains.reports.infrastructure.repository import (
    PostgreSQLReportRepository,
)
from app.models.orm_models import (
    ActivityStatus,
    Attachment,
    AttachmentStatus,
    AuditEvent,
    Channel,
    Group,
    GroupType,
    MemberRole,
    Membership,
    Message,
    ReportActivityEvent,
    User,
    UserRole,
)

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    (
        "postgresql+psycopg://"
        "spc_backend:spc_local_password@postgres:5432/spc_auth_test"
    ),
)

PNG_BYTES = b"\x89PNG\r\n\x1a\nintegration-proof"


async def _reset_tables(engine) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                TRUNCATE TABLE
                    report_activity_events,
                    report_notes,
                    evidence,
                    user_reports,
                    audit_events,
                    attachments,
                    messages,
                    channels,
                    memberships,
                    groups,
                    users
                RESTART IDENTITY CASCADE
                """
            )
        )


@pytest.mark.asyncio
async def test_postgresql_report_and_admin_governance_workflow() -> None:
    """Verify atomic snapshots, duplicate prevention, governance audit, and read-only closure."""

    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(
        engine, expire_on_commit=False, autoflush=False
    )
    now = datetime(2026, 11, 3, 12, 0, 0, tzinfo=timezone.utc)

    try:
        await _reset_tables(engine)

        admin_1_id = uuid.uuid4()
        admin_2_id = uuid.uuid4()
        reporter_id = uuid.uuid4()
        author_id = uuid.uuid4()
        outsider_id = uuid.uuid4()
        group_id = uuid.uuid4()
        channel_id = uuid.uuid4()

        async with session_factory() as seed:
            for uid, role, name in [
                (admin_1_id, UserRole.ADMIN, "Admin One"),
                (admin_2_id, UserRole.ADMIN, "Admin Two"),
                (reporter_id, UserRole.STUDENT, "Reporter Student"),
                (author_id, UserRole.STUDENT, "Author Student"),
                (outsider_id, UserRole.STUDENT, "Outsider Student"),
            ]:
                seed.add(
                    User(
                        user_id=uid,
                        email=f"{uid.hex[:8]}@example.com",
                        fullname=name,
                        password_hash="hashed-secret",
                        user_role=role,
                        status=ActivityStatus.ACTIVE,
                        created_at=now,
                    )
                )
            await seed.flush()

            seed.add(
                Group(
                    group_id=group_id,
                    group_name="COMP3851A Group",
                    group_type=GroupType.PRIVATE,
                    created_by=author_id,
                    current_owner=author_id,
                    max_members=10,
                    created_at=now,
                )
            )
            seed.add(
                Membership(
                    user_id=author_id,
                    group_id=group_id,
                    member_role=MemberRole.OWNER,
                    joined_at=now,
                )
            )
            seed.add(
                Membership(
                    user_id=reporter_id,
                    group_id=group_id,
                    member_role=MemberRole.MEMBER,
                    joined_at=now,
                )
            )
            seed.add(
                Channel(
                    channel_id=channel_id,
                    channel_name="general",
                    group_id=group_id,
                    created_by=author_id,
                    created_at=now,
                )
            )
            await seed.flush()

            created_messages: list[Message] = []
            for idx in range(7):
                m = Message(
                    user_id=author_id if idx == 3 else reporter_id,
                    channel_id=channel_id,
                    message_content=f"msg-{idx}",
                    sent_at=now + timedelta(seconds=idx),
                )
                seed.add(m)
                created_messages.append(m)

            att = Attachment(
                uploaded_by=author_id,
                channel_id=channel_id,
                group_id=group_id,
                title="Shared Doc",
                file_name="shared.pdf",
                file_type="application/pdf",
                file_size_bytes=512,
                object_path="/private/notes/shared.pdf",
                processing_status=AttachmentStatus.FAILED,
                processing_progress=0,
                processing_error="Failed reading /private/notes/shared.pdf",
                show_in_library=False,
                uploaded_at=now,
            )
            seed.add(att)
            await seed.commit()

            target_message_id = created_messages[3].message_id
            target_file_id = att.attachment_id

        # Outsider cannot report private group message
        async with session_factory() as session:
            report_repo = PostgreSQLReportRepository(session)
            with pytest.raises(ReportPermissionDeniedError):
                await report_repo.create_report(
                    reporter_user_id=str(outsider_id),
                    target_type=ReportTargetType.MESSAGE,
                    target_id=str(target_message_id),
                    category=ReportCategory.HARASSMENT_BULLYING,
                    description="Outsider attempting unauthorized report.",
                    include_limited_context=True,
                    evidence=[],
                )

        # Member creates message report with bounded +/-2 context & duplicate check
        async with session_factory() as session:
            report_repo = PostgreSQLReportRepository(session)
            msg_report = await report_repo.create_report(
                reporter_user_id=str(reporter_id),
                target_type=ReportTargetType.MESSAGE,
                target_id=str(target_message_id),
                category=ReportCategory.HARASSMENT_BULLYING,
                description="Harassing message inside study group.",
                include_limited_context=True,
                evidence=[
                    EvidenceUpload("proof.png", "image/png", PNG_BYTES)
                ],
            )
            assert msg_report.target_snapshot["message_text"] == "msg-3"
            assert [
                item["message_text"]
                for item in msg_report.limited_context_snapshot
            ] == ["msg-1", "msg-2", "msg-4", "msg-5"]

            with pytest.raises(DuplicateReportError):
                await report_repo.create_report(
                    reporter_user_id=str(reporter_id),
                    target_type=ReportTargetType.MESSAGE,
                    target_id=str(target_message_id),
                    category=ReportCategory.SPAM_SCAM,
                    description="Duplicate active report for same message.",
                    include_limited_context=False,
                    evidence=[],
                )

            file_report = await report_repo.create_report(
                reporter_user_id=str(reporter_id),
                target_type=ReportTargetType.FILE,
                target_id=str(target_file_id),
                category=ReportCategory.INAPPROPRIATE_CONTENT,
                description="Inappropriate shared PDF file.",
                include_limited_context=False,
                evidence=[],
            )
            assert file_report.target_snapshot["attachment_id"] == target_file_id
            assert "file_path" not in file_report.target_snapshot

            # Submitter scoping: outsider sees nothing
            outsider_page = await report_repo.list_reports(
                reporter_user_id=str(outsider_id),
                status=None,
                cursor=None,
                limit=10,
            )
            assert outsider_page.items == []
            assert (
                await report_repo.get_report(
                    reporter_user_id=str(outsider_id),
                    report_id=msg_report.report_id,
                )
                is None
            )

        # Admin workflow: start review -> note -> evidence view x2 -> action -> resolve
        async with session_factory() as session:
            admin_repo = PostgreSQLAdministrationRepository(session)
            actor = AdministrationActor(
                user_id=str(admin_1_id),
                reason="Confirmed policy breach during moderation",
            )

            started = await admin_repo.start_report_review(
                report_id=msg_report.report_id,
                actor=actor,
            )
            assert started is not None
            assert started.report.status == ReportStatus.UNDER_REVIEW

            noted = await admin_repo.add_report_note(
                report_id=msg_report.report_id,
                administrator_user_id=str(admin_2_id),
                note="Second admin corroborated context.",
            )
            assert noted is not None

            ev_id = msg_report.evidence[0].evidence_id
            await admin_repo.get_report_evidence(
                report_id=msg_report.report_id,
                evidence_id=ev_id,
                administrator_user_id=str(admin_1_id),
            )
            await admin_repo.get_report_evidence(
                report_id=msg_report.report_id,
                evidence_id=ev_id,
                administrator_user_id=str(admin_2_id),
            )

            action_res = await admin_repo.perform_report_governance_action(
                report_id=msg_report.report_id,
                action=AdminReportGovernanceAction.REMOVE_MESSAGE,
                actor=actor,
            )
            assert action_res is not None
            assert action_res.resource_id == str(target_message_id)
            assert action_res.status == "removed"

            resolved = await admin_repo.resolve_report(
                report_id=msg_report.report_id,
                administrator_user_id=str(admin_1_id),
                outcome=AdminReportResolutionOutcome.CONTENT_REMOVED,
                internal_reason="Message removed for harassment.",
                public_summary="The reported message was removed after review.",
            )
            assert resolved is not None
            assert resolved.report.status == ReportStatus.RESOLVED
            assert resolved.resolved_at is not None

            with pytest.raises(AdministrationConflictError):
                await admin_repo.add_report_note(
                    report_id=msg_report.report_id,
                    administrator_user_id=str(admin_1_id),
                    note="Cannot mutate resolved report.",
                )

            audit_page = await admin_repo.list_system_logs(
                severity=None,
                service=None,
                request_id=None,
                occurred_from=None,
                occurred_to=None,
                cursor=None,
                limit=10,
            )
            assert len(audit_page.items) == 1

            activities = (
                await session.scalars(
                    select(ReportActivityEvent).where(
                        ReportActivityEvent.report_id
                        == uuid.UUID(msg_report.report_id)
                    )
                )
            ).all()
            assert len(activities) == 6

            audits = (await session.scalars(select(AuditEvent))).all()
            assert len(audits) == 1
    finally:
        await engine.dispose()
