"""Real PostgreSQL checks in a disposable schema, never existing app tables.

Set SPC_TEST_DATABASE_URL to a PostgreSQL test database with pgvector installed.
The test account must be allowed to create schemas. No test database is assumed.
"""

import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domains.study_groups.infrastructure.repository import PostgreSQLStudyGroupRepository
from app.models.orm_models import ActivityStatus, User, UserRole
from app.domains.study_groups.domain.models import StudyGroupVisibility, StudyGroupMemberRole


@pytest_asyncio.fixture
async def sessions():
    url = os.environ.get("SPC_TEST_DATABASE_URL")
    if not url:
        pytest.skip("SPC_TEST_DATABASE_URL is required for PostgreSQL integration tests")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    schema = "spc_test_" + uuid4().hex
    admin = create_async_engine(url)
    engine = create_async_engine(
        url, connect_args={"options": f"-csearch_path={schema},public"},
    )
    try:
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        sql = (Path(__file__).resolve().parents[2] / "migrations" /
               "005_create_initial_test_schema.sql").read_text()
        # pgvector is a database prerequisite; tests create only their own schema.
        sql = sql.replace("create extension if not exists vector;", "")
        async with engine.begin() as connection:
            for statement in sql.split(";"):
                if statement.strip():
                    await connection.exec_driver_sql(statement)
        yield async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await admin.dispose()


async def add_user(session, *, email="member@example.com", status=ActivityStatus.ACTIVE,
                   deleted=False):
    user = User(
        email=email, fullname="Test Student", password_hash="private-hash",
        user_role=UserRole.STUDENT, status=status,
        created_at=datetime.now(timezone.utc),
        deleted_at=datetime.now(timezone.utc) if deleted else None,
    )
    session.add(user)
    await session.commit()
    # Rollback expires ORM instances, even with expire_on_commit=False.
    # Keep fixture identities usable after intentionally rejected operations.
    from types import SimpleNamespace
    return SimpleNamespace(user_id=user.user_id)


@pytest.mark.asyncio
async def test_email_lookup_is_case_insensitive_and_excludes_inactive_users(sessions):
    async with sessions() as session:
        active = await add_user(session, email="Student@Example.com")
        await add_user(session, email="disabled@example.com", status=ActivityStatus.DEACTIVATED)
        await add_user(session, email="deleted@example.com", deleted=True)
        repo = PostgreSQLStudyGroupRepository(session)
        assert await repo.find_active_user_id_by_email(email=" STUDENT@example.COM ") == str(active.user_id)
        for email in ("disabled@example.com", "deleted@example.com", "missing@example.com", "%@example.com"):
            assert await repo.find_active_user_id_by_email(email=email) is None


async def add_group(session, owner, *, name="Group", visibility=StudyGroupVisibility.PUBLIC,
                    max_members=20):
    return await PostgreSQLStudyGroupRepository(session).create_group(
        name=name, description=None, visibility=visibility,
        created_by=str(owner.user_id), max_members=max_members,
    )


@pytest.mark.asyncio
async def test_member_projection_pagination_and_deleted_group(sessions):
    from dataclasses import asdict
    async with sessions() as session:
        owner = await add_user(session, email="owner@example.com")
        member = await add_user(session)
        disabled = await add_user(session, email="disabled@example.com", status=ActivityStatus.DEACTIVATED)
        deleted = await add_user(session, email="deleted@example.com", deleted=True)
        group = await add_group(session, owner)
        repo = PostgreSQLStudyGroupRepository(session)
        gid = group.group.group_id
        for user in (member, disabled, deleted):
            await repo.create_membership(group_id=gid, user_id=str(user.user_id),
                role=StudyGroupMemberRole.MEMBER, joined_at=datetime.now(timezone.utc))
        first, total = await repo.list_members(group_id=gid, offset=0, limit=1)
        second, total2 = await repo.list_members(group_id=gid, offset=1, limit=1)
        assert total == total2 == 2
        assert first[0].user_id == str(owner.user_id)
        assert second[0].user_id == str(member.user_id)
        assert set(asdict(first[0])) == {
            "membership_id", "group_id", "user_id", "full_name", "email", "role", "joined_at",
        }
        await repo.soft_delete_group(group_id=gid, deleted_at=datetime.now(timezone.utc))
        assert await repo.list_members(group_id=gid, offset=0, limit=10) == ([], 0)


async def add_channel(repo, group, owner, *, name="Discussion"):
    return await repo.create_channel(
        group_id=group.group.group_id, name=name, description=None,
        created_by=str(owner.user_id), created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_channel_scope_names_pagination_and_soft_deletion(sessions):
    from app.domains.study_groups.domain.exceptions import (
        StudyGroupChannelNameConflictError, StudyGroupChannelNotFoundError,
    )
    from app.models.orm_models import Channel
    async with sessions() as session:
        owner = await add_user(session)
        group = await add_group(session, owner)
        other = await add_group(session, owner, name="Private", visibility=StudyGroupVisibility.PRIVATE)
        repo = PostgreSQLStudyGroupRepository(session)
        channel = await add_channel(repo, group, owner)
        gid, cid = group.group.group_id, channel.channel_id
        assert await repo.get_channel(group_id=gid, channel_id=cid) == channel
        await add_channel(repo, other, owner, name="DISCUSSION")
        with pytest.raises(StudyGroupChannelNameConflictError):
            await add_channel(repo, group, owner, name="discussion")
        assert await repo.get_channel(group_id=other.group.group_id, channel_id=cid) is None
        with pytest.raises(StudyGroupChannelNotFoundError):
            await repo.update_channel(group_id=other.group.group_id, channel_id=cid,
                name="Wrong", description=None, updated_at=datetime.now(timezone.utc))
        assert not await repo.soft_delete_channel(group_id=other.group.group_id,
            channel_id=cid, deleted_at=datetime.now(timezone.utc))
        assert not await repo.channel_name_exists(group_id=gid, normalized_name="discussion", exclude_channel_id=cid)
        renamed = await repo.update_channel(group_id=gid, channel_id=cid,
            name="DISCUSSION", description="Changed", updated_at=datetime.now(timezone.utc))
        assert renamed.name == "DISCUSSION"
        second_channel = await add_channel(repo, group, owner, name="Second")
        with pytest.raises(StudyGroupChannelNameConflictError):
            await repo.update_channel(group_id=gid, channel_id=second_channel.channel_id,
                name="discussion", description=None, updated_at=datetime.now(timezone.utc))
        assert (await repo.get_channel(group_id=gid, channel_id=second_channel.channel_id)).name == "Second"
        page, total = await repo.list_channels(group_id=gid, offset=1, limit=1)
        assert total == 2 and len(page) == 1
        assert await repo.soft_delete_channel(group_id=gid, channel_id=cid, deleted_at=datetime.now(timezone.utc))
        assert (await session.get(Channel, UUID(cid))).deleted_at is not None
        assert await repo.get_channel(group_id=gid, channel_id=cid) is None
        assert not await repo.channel_name_exists(group_id=gid, normalized_name="discussion")
        await add_channel(repo, group, owner, name="discussion")
        await repo.soft_delete_group(group_id=gid, deleted_at=datetime.now(timezone.utc))
        assert await repo.list_channels(group_id=gid, offset=0, limit=10) == ([], 0)


async def add_message(repo, group, channel, owner, *, content="Question", mentions=(), mode=None, sent_at=None):
    return await repo.create_message(
        group_id=group.group.group_id, channel_id=channel.channel_id,
        author_id=str(owner.user_id), content=content, mentioned_user_ids=mentions,
        ai_mode=mode, sent_at=sent_at or datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_messages_enforce_scope_order_pagination_and_soft_deletion(sessions):
    from datetime import timedelta
    from app.domains.study_groups.domain.exceptions import StudyGroupMessageNotFoundError
    from app.models.orm_models import Message
    async with sessions() as session:
        owner = await add_user(session)
        group = await add_group(session, owner)
        other = await add_group(session, owner, name="Other")
        repo = PostgreSQLStudyGroupRepository(session)
        channel = await add_channel(repo, group, owner)
        channel2 = await add_channel(repo, group, owner, name="Other channel")
        scope = dict(group_id=group.group.group_id, channel_id=channel.channel_id)
        now = datetime.now(timezone.utc)
        later = await add_message(repo, group, channel, owner, content="Later", sent_at=now)
        first = await add_message(repo, group, channel, owner, content="First", sent_at=now-timedelta(seconds=1))
        page, total = await repo.list_messages(**scope, offset=0, limit=1)
        assert total == 2 and page[0].message_id == first.message_id
        assert page[0].ai_mode_used is None
        assert first.author_id == str(owner.user_id)
        assert await repo.get_message(**scope, message_id=first.message_id) == first
        next_page, next_total = await repo.list_messages(**scope, offset=1, limit=1)
        assert next_total == 2 and next_page == [later]
        for wrong in (
            dict(group_id=other.group.group_id, channel_id=channel.channel_id),
            dict(group_id=group.group.group_id, channel_id=channel2.channel_id),
        ):
            assert await repo.get_message(**wrong, message_id=first.message_id) is None
            with pytest.raises(StudyGroupMessageNotFoundError):
                await repo.update_message(**wrong, message_id=first.message_id,
                    content="Forbidden", mentioned_user_ids=(), edited_at=now)
            assert not await repo.soft_delete_message(**wrong, message_id=first.message_id, deleted_at=now)
        changed = await repo.update_message(**scope, message_id=first.message_id,
            content="Edited", mentioned_user_ids=(), edited_at=now)
        assert changed.content == "Edited" and changed.edited_at == now
        assert await repo.soft_delete_message(**scope, message_id=first.message_id, deleted_at=now)
        assert (await session.get(Message, first.message_id)).deleted_at is not None
        assert await repo.get_message(**scope, message_id=first.message_id) is None
        assert (await repo.list_messages(**scope, offset=0, limit=10))[1] == 1
        await repo.soft_delete_channel(**scope, deleted_at=now)
        assert await repo.get_message(**scope, message_id=later.message_id) is None
        assert await repo.list_messages(**scope, offset=0, limit=10) == ([], 0)


@pytest.mark.asyncio
async def test_mentions_round_trip_replace_rollback_and_fk_cascade(sessions):
    from sqlalchemy import delete, func
    from sqlalchemy.exc import IntegrityError
    from app.models.orm_models import Message, MessageMention
    async with sessions() as session:
        owner = await add_user(session, email="owner@example.com")
        first = await add_user(session, email="first@example.com")
        second = await add_user(session, email="second@example.com")
        group = await add_group(session, owner)
        repo = PostgreSQLStudyGroupRepository(session)
        channel = await add_channel(repo, group, owner)
        scope = dict(group_id=group.group.group_id, channel_id=channel.channel_id)
        message = await add_message(repo, group, channel, owner,
            mentions=(str(first.user_id), str(first.user_id)))
        assert message.mentioned_user_ids == (str(first.user_id),)
        assert (await repo.get_message(**scope, message_id=message.message_id)).mentioned_user_ids == (str(first.user_id),)
        changed = await repo.update_message(**scope, message_id=message.message_id,
            content="Second mention", mentioned_user_ids=(str(second.user_id),),
            edited_at=datetime.now(timezone.utc))
        assert changed.mentioned_user_ids == (str(second.user_id),)
        with pytest.raises(IntegrityError):
            await repo.update_message(**scope, message_id=message.message_id,
                content="Must roll back", mentioned_user_ids=(str(uuid4()),),
                edited_at=datetime.now(timezone.utc))
        unchanged = await repo.get_message(**scope, message_id=message.message_id)
        assert unchanged.content == "Second mention"
        assert unchanged.mentioned_user_ids == (str(second.user_id),)
        with pytest.raises(IntegrityError):
            await add_message(repo, group, channel, owner, mentions=(str(uuid4()),))
        assert (await repo.list_messages(**scope, offset=0, limit=10))[1] == 1
        session.add(MessageMention(message_id=message.message_id, user_id=second.user_id))
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()
        await repo.soft_delete_message(**scope, message_id=message.message_id,
            deleted_at=datetime.now(timezone.utc))
        # Soft deletion retains valid history; hard deletion cascades the joins.
        assert await session.scalar(select(func.count()).select_from(MessageMention)) == 1
        await session.execute(delete(Message).where(Message.message_id == message.message_id))
        await session.commit()
        assert await session.scalar(select(func.count()).select_from(MessageMention)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", [None, "default", "summarizer", "quiz", "facilitator"])
async def test_websocket_payload_matches_committed_history_at_publication(sessions, monkeypatch, mode):
    import importlib
    from types import SimpleNamespace
    from app.domains.study_groups.application.services import StudyGroupService
    from app.domains.study_groups.infrastructure.retrieval import PostgreSQLStudyGroupReadyChunkRepository
    from app.domains.chats.infrastructure.memory_answering import LocalGroundedAnswerGenerator
    from app.domains.study_groups.presentation.schemas import (
        CreateStudyGroupMessageRequest, UpdateStudyGroupMessageRequest, StudyGroupMessageResponse,
    )
    from app.models.orm_models import Message
    routes = importlib.import_module("app.domains.study_groups.presentation.router")
    published = []

    async def assert_committed_broadcast(*, group_id, channel_id, event):
        # This separate connection cannot see an uncommitted writer's rows.
        async with sessions() as reader:
            repo = PostgreSQLStudyGroupRepository(reader)
            deleted = event["type"] == "study_group.message.deleted"
            message_id = event["data"]["message_id" if deleted else "id"]
            message = await repo.get_message(group_id=group_id, channel_id=channel_id, message_id=message_id)
            history, _ = await repo.list_messages(group_id=group_id, channel_id=channel_id, offset=0, limit=50)
            if deleted:
                assert message is None
                assert all(item.message_id != message_id for item in history)
                row = await reader.get(Message, message_id)
                assert row is not None and row.deleted_at is not None
            else:
                assert message is not None
                assert StudyGroupMessageResponse.from_message(message).model_dump(mode="json") == event["data"]
                assert next(item for item in history if item.message_id == message_id) == message
        published.append(event)

    monkeypatch.setattr(routes.study_group_connections, "broadcast", assert_committed_broadcast)
    async with sessions() as session:
        owner = await add_user(session)
        mentioned = await add_user(session, email="mentioned@example.com")
        repo = PostgreSQLStudyGroupRepository(session)
        group = await add_group(session, owner)
        await add_membership(repo, group, mentioned)
        channel = await add_channel(repo, group, owner)
        source = await add_chunk(session, owner, group, channel)
        service = StudyGroupService(repo,
            chunk_repository=PostgreSQLStudyGroupReadyChunkRepository(session),
            answer_generator=LocalGroundedAnswerGenerator())
        args = dict(group_id=UUID(group.group.group_id), channel_id=UUID(channel.channel_id),
            current_user=SimpleNamespace(id=str(owner.user_id)), service=service)
        response = await routes.create_group_message(**args, payload=CreateStudyGroupMessageRequest(
            content="Explain the channel content", mentioned_user_ids=[mentioned.user_id], ai_mode=mode))
        assert published[-1]["type"] == "study_group.message.created"
        assert published[-1]["data"] == response.model_dump(mode="json")
        assert response.mentioned_user_ids == [str(mentioned.user_id)]
        if mode is not None:
            assert response.ai_mode_used.value == mode
            assert response.ai_response.mode.value == mode
            assert response.ai_response.sources[0].chunk_id == source.chunk_id
        else:
            assert response.ai_mode_used is None and response.ai_response is None
            response = await routes.update_group_message(**args, message_id=response.id,
                payload=UpdateStudyGroupMessageRequest(content="Edited content", mentioned_user_ids=[]))
            assert published[-1]["type"] == "study_group.message.updated"
            assert published[-1]["data"] == response.model_dump(mode="json")
            assert response.mentioned_user_ids == [] and response.edited_at is not None
        await routes.delete_group_message(**args, message_id=response.id)
        assert published[-1]["type"] == "study_group.message.deleted"
        expected = ["study_group.message.created"]
        if mode is None:
            expected.append("study_group.message.updated")
        assert [event["type"] for event in published] == expected + ["study_group.message.deleted"]


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["create", "update", "delete", "ai_response"])
async def test_commit_time_failure_rolls_back_without_publishing_a_websocket_event(sessions, monkeypatch, operation):
    import importlib
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from sqlalchemy import func
    from sqlalchemy.exc import IntegrityError
    from app.api.error_handlers import ApiError
    from app.domains.study_groups.application.services import StudyGroupService
    from app.domains.study_groups.infrastructure.retrieval import PostgreSQLStudyGroupReadyChunkRepository
    from app.domains.chats.infrastructure.memory_answering import LocalGroundedAnswerGenerator
    from app.domains.study_groups.presentation.schemas import CreateStudyGroupMessageRequest, UpdateStudyGroupMessageRequest
    from app.models.orm_models import Message, MessageMention, AIResponse, AIResponseSource
    routes = importlib.import_module("app.domains.study_groups.presentation.router")
    broadcast = AsyncMock()
    monkeypatch.setattr(routes.study_group_connections, "broadcast", broadcast)
    async with sessions() as session:
        owner = await add_user(session)
        mentioned = await add_user(session, email="mentioned@example.com")
        repo = PostgreSQLStudyGroupRepository(session)
        group = await add_group(session, owner)
        await add_membership(repo, group, mentioned)
        channel = await add_channel(repo, group, owner)
        original = None
        if operation in ("update", "delete"):
            original = await add_message(repo, group, channel, owner,
                content="Original", mentions=(str(mentioned.user_id),))
        if operation == "ai_response":
            await add_chunk(session, owner, group, channel)
        # A deferred constraint trigger allows every INSERT/UPDATE and flush
        # to succeed, then raises inside COMMIT. It exists only in this test schema.
        await session.execute(text("""
            CREATE FUNCTION reject_test_message_commit() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'forced message commit failure' USING ERRCODE = '23514';
                RETURN NEW;
            END;
            $$
        """))
        table = "ai_responses" if operation == "ai_response" else "messages"
        await session.execute(text(f"""
            CREATE CONSTRAINT TRIGGER reject_test_message_commit
            AFTER INSERT OR UPDATE ON {table}
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
            EXECUTE FUNCTION reject_test_message_commit()
        """))
        await session.commit()
        service = StudyGroupService(repo,
            chunk_repository=PostgreSQLStudyGroupReadyChunkRepository(session),
            answer_generator=LocalGroundedAnswerGenerator())
        args = dict(group_id=UUID(group.group.group_id), channel_id=UUID(channel.channel_id),
            current_user=SimpleNamespace(id=str(owner.user_id)), service=service)
        with pytest.raises(ApiError if operation == "ai_response" else IntegrityError) as error:
            if operation in ("create", "ai_response"):
                await routes.create_group_message(**args, payload=CreateStudyGroupMessageRequest(
                    content="Explain the channel content", mentioned_user_ids=[mentioned.user_id],
                    ai_mode="default" if operation == "ai_response" else None))
            elif operation == "update":
                await routes.update_group_message(**args, message_id=original.message_id,
                    payload=UpdateStudyGroupMessageRequest(content="Must roll back", mentioned_user_ids=[]))
            else:
                await routes.delete_group_message(**args, message_id=original.message_id)
        if operation == "ai_response":
            assert error.value.code == "STUDY_GROUP_ANSWER_GENERATION_FAILED"
            assert isinstance(error.value.__cause__.__cause__, IntegrityError)
        else:
            assert "forced message commit failure" in str(error.value)
        broadcast.assert_not_awaited()

    async with sessions() as reader:
        repo = PostgreSQLStudyGroupRepository(reader)
        history, total = await repo.list_messages(group_id=group.group.group_id,
            channel_id=channel.channel_id, offset=0, limit=10)
        if operation == "create":
            assert total == 0 and history == []
            assert await reader.scalar(select(func.count()).select_from(MessageMention)) == 0
        elif operation == "ai_response":
            # The existing service commits the student's question separately.
            # Failed AI persistence must not emit a completed created event.
            assert total == 1 and history[0].ai_response is None
            assert history[0].mentioned_user_ids == (str(mentioned.user_id),)
            assert await reader.scalar(select(func.count()).select_from(AIResponse)) == 0
            assert await reader.scalar(select(func.count()).select_from(AIResponseSource)) == 0
        else:
            assert total == 1 and history[0] == original
            assert (await reader.get(Message, original.message_id)).deleted_at is None


async def add_chunk(session, owner, group, channel, *, status=None, deleted_attachment=False, deleted_chunk=False):
    from app.models.orm_models import Attachment, AttachmentStatus, Chunk
    now = datetime.now(timezone.utc)
    attachment = Attachment(
        uploaded_by=owner.user_id, group_id=UUID(group.group.group_id) if group else None,
        channel_id=UUID(channel.channel_id) if channel else None,
        title="Source", file_name="source.pdf", file_type="application/pdf",
        file_size_bytes=100, object_path="/private/source.pdf",
        processing_status=status or AttachmentStatus.READY, processing_progress=100,
        uploaded_at=now, deleted_at=now if deleted_attachment else None,
    )
    session.add(attachment)
    await session.flush()
    chunk = Chunk(
        attachment_id=attachment.attachment_id, chunk_order=0, source_page=1,
        source_type="text", chunk_content="Channel-specific content",
        embedding_model_version="test", vector_embedding=[0.1] * 768,
        created_at=now, deleted_at=now if deleted_chunk else None,
    )
    session.add(chunk)
    await session.commit()
    from app.domains.chats.domain.models import ChatSource
    return ChatSource(note_id=attachment.attachment_id, note_title=attachment.title,
                      chunk_id=chunk.chunk_id, page=1)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["default", "summarizer", "quiz", "facilitator"])
async def test_ai_modes_selected_answer_and_scoped_citations(sessions, mode):
    from app.domains.study_groups.domain.models import StudyGroupAiMode
    from app.domains.study_groups.domain.exceptions import InvalidStudyGroupMessageError, StudyGroupMessageNotFoundError
    from app.models.orm_models import AIResponse
    async with sessions() as session:
        owner = await add_user(session)
        group = await add_group(session, owner)
        other = await add_group(session, owner, name="Other")
        repo = PostgreSQLStudyGroupRepository(session)
        channel = await add_channel(repo, group, owner)
        other_channel = await add_channel(repo, other, owner)
        source = await add_chunk(session, owner, group, channel)
        outside = await add_chunk(session, owner, other, other_channel)
        message = await add_message(repo, group, channel, owner, mode=StudyGroupAiMode(mode))
        scope = dict(group_id=group.group.group_id, channel_id=channel.channel_id, message_id=message.message_id)
        pending = await repo.get_message(**scope)
        assert pending.ai_mode_used == StudyGroupAiMode(mode) and pending.ai_response is None
        now = datetime.now(timezone.utc)
        for content in ("First answer", "Selected answer"):
            saved = await repo.save_ai_response(**scope, mode=StudyGroupAiMode(mode),
                content=content, sources=(source,), generated_at=now)
            assert saved.ai_response.content == content
            assert saved.ai_response.sources == (source,)
        responses = (await session.scalars(select(AIResponse).where(AIResponse.message_id == message.message_id))).all()
        assert len(responses) == 2 and sum(r.is_selected for r in responses) == 1
        with pytest.raises(InvalidStudyGroupMessageError):
            await repo.save_ai_response(**scope, mode=StudyGroupAiMode(mode),
                content="Invalid source", sources=(outside,), generated_at=now)
        assert (await repo.get_message(**scope)).ai_response.content == "Selected answer"
        with pytest.raises(StudyGroupMessageNotFoundError):
            await repo.save_ai_response(group_id=other.group.group_id, channel_id=channel.channel_id,
                message_id=message.message_id, mode=StudyGroupAiMode(mode), content="Wrong group",
                sources=(), generated_at=now)
    async with sessions() as session:
        from app.models.orm_models import AIResponseSource, Message
        reloaded = await PostgreSQLStudyGroupRepository(session).get_message(**scope)
        assert reloaded.ai_mode_used == StudyGroupAiMode(mode)
        assert reloaded.ai_response.mode == StudyGroupAiMode(mode)
        assert reloaded.ai_response.content == "Selected answer"
        assert reloaded.ai_response.generated_at == now
        assert reloaded.ai_response.sources == (source,)
        assert (await session.get(Message, message.message_id)).ai_mode_used.value == mode
        citation = await session.scalar(select(AIResponseSource).where(
            AIResponseSource.response_id == reloaded.ai_response.response_id))
        assert citation.chunk_id == source.chunk_id


@pytest.mark.asyncio
@pytest.mark.parametrize("visibility", [StudyGroupVisibility.PUBLIC, StudyGroupVisibility.PRIVATE])
async def test_ready_chunks_enforce_channel_group_and_active_boundaries(sessions, visibility):
    from app.domains.study_groups.infrastructure.retrieval import PostgreSQLStudyGroupReadyChunkRepository
    from app.models.orm_models import AttachmentStatus
    async with sessions() as session:
        owner = await add_user(session)
        group = await add_group(session, owner, visibility=visibility)
        other = await add_group(session, owner, name="Other")
        repo = PostgreSQLStudyGroupRepository(session)
        channel = await add_channel(repo, group, owner)
        sibling = await add_channel(repo, group, owner, name="Sibling")
        outside = await add_channel(repo, other, owner)
        expected = await add_chunk(session, owner, group, channel)
        await add_chunk(session, owner, group, sibling)
        await add_chunk(session, owner, other, outside)
        await add_chunk(session, owner, None, None)
        for status in (AttachmentStatus.QUEUED, AttachmentStatus.PROCESSING, AttachmentStatus.FAILED):
            await add_chunk(session, owner, group, channel, status=status)
        await add_chunk(session, owner, group, channel, deleted_attachment=True)
        await add_chunk(session, owner, group, channel, deleted_chunk=True)
        retrieval = PostgreSQLStudyGroupReadyChunkRepository(session)
        scope = dict(group_id=group.group.group_id, channel_id=channel.channel_id)
        chunks = await retrieval.list_ready_chunks_for_channel(**scope)
        assert tuple(chunk.source for chunk in chunks) == (expected,)
        assert chunks[0].content == "Channel-specific content"
        assert await retrieval.list_ready_chunks_for_channel(
            group_id=other.group.group_id, channel_id=channel.channel_id) == ()
        assert await retrieval.list_ready_chunks_for_channel(group_id="invalid", channel_id="invalid") == ()
        await repo.soft_delete_channel(**scope, deleted_at=datetime.now(timezone.utc))
        assert await retrieval.list_ready_chunks_for_channel(**scope) == ()
        await repo.soft_delete_group(group_id=group.group.group_id, deleted_at=datetime.now(timezone.utc))
        assert await retrieval.list_ready_chunks_for_channel(
            group_id=group.group.group_id, channel_id=sibling.channel_id) == ()


async def add_personal_group(session, owner):
    from app.models.orm_models import Group, GroupType
    group = Group(
        group_name="Personal", group_type=GroupType.PERSONAL,
        created_by=owner.user_id, current_admin=owner.user_id,
        max_members=1, created_at=datetime.now(timezone.utc),
    )
    session.add(group)
    await session.commit()
    return group.group_id


@pytest.mark.asyncio
async def test_personal_chat_existing_service_automatically_names_first_question(sessions):
    from app.domains.chats.application.services import ChatService
    from app.domains.chats.domain.retrieval import GroundingChunk
    from app.domains.chats.infrastructure.memory_answering import LocalGroundedAnswerGenerator
    from app.domains.chats.infrastructure.memory_retrieval import InMemoryReadyNoteChunkRepository
    from app.domains.chats.infrastructure.repository import PostgreSQLChatRepository
    from app.models.orm_models import Channel
    async with sessions() as session:
        owner = await add_user(session)
        await add_personal_group(session, owner)
        source = await add_chunk(session, owner, None, None)
        chunks = InMemoryReadyNoteChunkRepository()
        await chunks.replace_user_chunks(user_id=str(owner.user_id), chunks=(
            GroundingChunk(content="Indexes make data lookup faster.", source=source),
        ))
        repo = PostgreSQLChatRepository(session)
        service = ChatService(repository=repo, chunk_repository=chunks,
            answer_generator=LocalGroundedAnswerGenerator(), maximum_question_length=2000)
        uid = str(owner.user_id)
        await service.create_chat(user_id=uid, title=None)
        chat = await service.create_chat(user_id=uid, title=None)
        assert chat.title == "New chat (2)"
        first = await service.ask_question(chat_id=chat.chat_id, user_id=uid,
            question="What is indexing?")
        assert first.chat.title == "What is indexing"
        stored = await session.get(Channel, UUID(chat.chat_id))
        assert stored.channel_name == first.chat.title
        assert stored.last_updated_at >= chat.updated_at
        page, count = await repo.list_messages(chat_id=chat.chat_id, offset=0, limit=1)
        assert count == 2 and len(page) == 1
        assert page[0].content == "What is indexing?"
        second = await service.ask_question(chat_id=chat.chat_id, user_id=uid,
            question="Explain database query planning.")
        assert second.chat.title == first.chat.title
        collision = await service.create_chat(user_id=uid, title=None)
        titled = await service.ask_question(chat_id=collision.chat_id, user_id=uid,
            question="What is indexing?")
        assert titled.chat.title == "What is indexing (2)"
        manual = await service.create_chat(user_id=uid, title="Revision notes")
        exchange = await service.ask_question(chat_id=manual.chat_id, user_id=uid,
            question="What is indexing?")
        assert exchange.chat.title == "Revision notes"


@pytest.mark.asyncio
async def test_personal_chat_ownership_counts_unique_rename_and_deletion(sessions):
    from app.domains.chats.domain.models import ChatMessageRole
    from app.domains.chats.infrastructure.repository import PostgreSQLChatRepository
    from app.models.orm_models import Channel, Group
    async with sessions() as session:
        owner = await add_user(session)
        outsider = await add_user(session, email="outsider@example.com")
        group_id = await add_personal_group(session, owner)
        await add_personal_group(session, outsider)
        repo = PostgreSQLChatRepository(session)
        uid, other_uid = str(owner.user_id), str(outsider.user_id)
        chat = await repo.create_chat(owner_id=uid, title="Revision")
        duplicate = await repo.create_chat(owner_id=uid, title="revision")
        assert duplicate.title == "revision (2)"
        assert (await repo.create_chat(owner_id=other_uid, title="Revision")).title == "Revision"
        assert await repo.get_owned_chat(chat_id=chat.chat_id, owner_id=other_uid) is None
        assert await repo.rename_owned_chat(chat_id=chat.chat_id, owner_id=other_uid, title="Forbidden") is None
        assert not await repo.soft_delete_owned_chat(chat_id=chat.chat_id, owner_id=other_uid,
            deleted_at=datetime.now(timezone.utc))
        assert await repo.list_messages(chat_id=chat.chat_id, offset=0, limit=1) == ([], 0)
        first = await repo.create_message(chat_id=chat.chat_id, role=ChatMessageRole.USER, content="First question")
        page, count = await repo.list_messages(chat_id=chat.chat_id, offset=0, limit=1)
        assert count == 1 and page[0] == first
        renamed = await repo.rename_owned_chat(chat_id=chat.chat_id, owner_id=uid, title="REVISION")
        assert renamed.title == "REVISION"  # Excludes itself from the duplicate check.
        assert renamed.updated_at >= first.created_at
        assert renamed.last_message_preview == "First question"
        timestamp = datetime.now(timezone.utc)
        assert await repo.soft_delete_owned_chat(chat_id=chat.chat_id, owner_id=uid, deleted_at=timestamp)
        assert (await session.get(Channel, UUID(chat.chat_id))).deleted_at == timestamp
        assert await repo.get_owned_chat(chat_id=chat.chat_id, owner_id=uid) is None
        assert await repo.list_messages(chat_id=chat.chat_id, offset=0, limit=1) == ([], 0)
        assert await repo.rename_owned_chat(chat_id=chat.chat_id, owner_id=uid, title="Hidden") is None
        with pytest.raises(ValueError):
            await repo.create_message(chat_id=chat.chat_id, role=ChatMessageRole.USER, content="Hidden")
        replacement = await repo.create_chat(owner_id=uid, title="Revision")
        assert replacement.title == "Revision"
        assert (await repo.list_owned_chats(owner_id=uid, offset=0, limit=1))[1] == 2
        group = await session.get(Group, group_id)
        group.deleted_at = timestamp
        await session.commit()
        assert await repo.get_owned_chat(chat_id=replacement.chat_id, owner_id=uid) is None
        assert await repo.list_owned_chats(owner_id=uid, offset=0, limit=10) == ([], 0)
        assert await repo.list_messages(chat_id=replacement.chat_id, offset=0, limit=10) == ([], 0)
        assert await repo.rename_owned_chat(chat_id=replacement.chat_id, owner_id=uid, title="Hidden") is None


@pytest.mark.asyncio
async def test_concurrent_personal_chat_names_are_unique(sessions):
    import asyncio
    from app.domains.chats.infrastructure.repository import PostgreSQLChatRepository
    async with sessions() as session:
        owner = await add_user(session)
        await add_personal_group(session, owner)

    async def create():
        async with sessions() as session:
            return await PostgreSQLChatRepository(session).create_chat(
                owner_id=str(owner.user_id), title="New chat")

    chats = await asyncio.wait_for(asyncio.gather(create(), create()), timeout=15)
    assert {chat.title for chat in chats} == {"New chat", "New chat (2)"}


async def add_membership(repo, group, user, *, role=StudyGroupMemberRole.MEMBER):
    return await repo.create_membership(
        group_id=group.group.group_id, user_id=str(user.user_id), role=role,
        joined_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_discovery_returns_only_active_public_groups_with_search_and_pagination(sessions):
    async with sessions() as session:
        owner = await add_user(session)
        visitor = await add_user(session, email="visitor@example.com")
        repo = PostgreSQLStudyGroupRepository(session)
        public = await add_group(session, owner, name="Database revision")
        literal = await add_group(session, owner, name="100%_ready")
        await add_group(session, owner, name="Private", visibility=StudyGroupVisibility.PRIVATE)
        await add_personal_group(session, owner)
        deleted = await add_group(session, owner, name="Deleted public")
        await repo.soft_delete_group(group_id=deleted.group.group_id, deleted_at=datetime.now(timezone.utc))
        args = dict(user_id=str(visitor.user_id), offset=0, limit=10)
        groups, total = await repo.list_discoverable_public_groups(**args)
        assert total == 2
        assert {g.group.group_id for g in groups} == {public.group.group_id, literal.group.group_id}
        assert all(not g.is_owner and not g.is_member for g in groups)
        page, page_total = await repo.list_discoverable_public_groups(**{**args, "offset": 1, "limit": 1})
        assert page_total == 2 and page == groups[1:2]
        found, total = await repo.list_discoverable_public_groups(**args, search="DATABASE")
        assert total == 1 and found[0].group.group_id == public.group.group_id
        found, total = await repo.list_discoverable_public_groups(**args, search="%_")
        assert total == 1 and found[0].group.group_id == literal.group.group_id


@pytest.mark.asyncio
@pytest.mark.parametrize("group_filter", ["all", "public", "private", "owned"])
async def test_my_groups_filters_include_owned_or_joined_active_nonpersonal_groups(sessions, group_filter):
    from sqlalchemy import delete
    from app.domains.study_groups.domain.models import MyGroupsFilter
    from app.models.orm_models import Group, Membership
    async with sessions() as session:
        user = await add_user(session)
        other = await add_user(session, email="other@example.com")
        repo = PostgreSQLStudyGroupRepository(session)
        owned_public = await add_group(session, user, name="Owned public")
        owned_private = await add_group(session, user, name="Owned private", visibility=StudyGroupVisibility.PRIVATE)
        joined_public = await add_group(session, other, name="Joined public")
        joined_private = await add_group(session, other, name="Joined private", visibility=StudyGroupVisibility.PRIVATE)
        for group in (joined_public, joined_private):
            await add_membership(repo, group, user)
        await add_group(session, other, name="Unjoined public")
        await add_group(session, other, name="Unjoined private", visibility=StudyGroupVisibility.PRIVATE)
        await add_personal_group(session, user)
        deleted = await add_group(session, user, name="Deleted")
        await repo.soft_delete_group(group_id=deleted.group.group_id, deleted_at=datetime.now(timezone.utc))
        # Ownership comes from created_by, even without a membership and when
        # current_admin points to somebody else.
        await session.execute(delete(Membership).where(Membership.group_id == UUID(owned_public.group.group_id)))
        row = await session.get(Group, UUID(owned_public.group.group_id))
        row.current_admin = other.user_id
        await session.commit()
        expected = {
            "all": (owned_public, owned_private, joined_public, joined_private),
            "public": (owned_public, joined_public),
            "private": (owned_private, joined_private),
            "owned": (owned_public, owned_private),
        }[group_filter]
        args = dict(user_id=str(user.user_id), group_filter=MyGroupsFilter(group_filter))
        groups, total = await repo.list_user_groups(**args, offset=0, limit=20)
        assert total == len(expected)
        assert {g.group.group_id for g in groups} == {g.group.group_id for g in expected}
        page, page_total = await repo.list_user_groups(**args, offset=1, limit=1)
        assert page_total == total and page == groups[1:2]
        owned = await repo.get_group_for_user(group_id=owned_public.group.group_id, user_id=str(user.user_id))
        assert owned.is_owner and not owned.is_member


@pytest.mark.asyncio
async def test_private_group_is_hidden_from_nonmembers_and_cannot_be_self_joined(sessions):
    from app.domains.study_groups.application.services import StudyGroupService
    from app.domains.study_groups.domain.exceptions import PrivateStudyGroupJoinError, StudyGroupNotFoundError
    async with sessions() as session:
        owner = await add_user(session)
        outsider = await add_user(session, email="outsider@example.com")
        repo = PostgreSQLStudyGroupRepository(session)
        service = StudyGroupService(repo)
        group = await add_group(session, owner, visibility=StudyGroupVisibility.PRIVATE)
        channel = await add_channel(repo, group, owner)
        message = await add_message(repo, group, channel, owner)
        scope = dict(group_id=group.group.group_id, user_id=str(outsider.user_id))
        assert await repo.get_group_for_user(**scope) is None
        with pytest.raises(PrivateStudyGroupJoinError):
            await service.join_public_group(**scope)
        with pytest.raises(StudyGroupNotFoundError):
            await service.list_channels(**scope, page=1, page_size=10)
        with pytest.raises(StudyGroupNotFoundError):
            await service.get_message(**scope, channel_id=channel.channel_id, message_id=message.message_id)
        await service.add_member_by_email(group_id=group.group.group_id,
            requester_user_id=str(owner.user_id), email="OUTSIDER@example.com")
        assert (await repo.get_group_for_user(**scope)).is_member
        assert (await service.get_message(**scope, channel_id=channel.channel_id,
            message_id=message.message_id)).content == message.content


@pytest.mark.asyncio
@pytest.mark.parametrize("visibility", [StudyGroupVisibility.PUBLIC, StudyGroupVisibility.PRIVATE])
async def test_group_and_initial_owner_admin_membership_are_committed_together(sessions, visibility):
    from app.models.orm_models import Group, Membership, MemberRole
    async with sessions() as session:
        owner = await add_user(session)
        created = await add_group(session, owner, visibility=visibility)
    # A new session proves both rows were committed, rather than only flushed.
    async with sessions() as session:
        group = await session.get(Group, UUID(created.group.group_id))
        membership = await session.scalar(select(Membership).where(Membership.group_id == group.group_id))
        assert group.created_by == owner.user_id
        assert membership.user_id == owner.user_id and membership.member_role == MemberRole.ADMIN
        assert created.is_owner and created.is_member and created.member_count == 1
        assert created.membership_role == StudyGroupMemberRole.ADMIN


@pytest.mark.asyncio
async def test_group_creation_rolls_back_if_initial_membership_insert_fails(sessions):
    from sqlalchemy import func
    from sqlalchemy.exc import IntegrityError
    from app.models.orm_models import Group, Membership
    async with sessions() as session:
        owner = await add_user(session)
        # Force a real database failure on the second insert, inside this
        # disposable test schema only. No repository methods are mocked.
        await session.execute(text("ALTER TABLE memberships ADD CONSTRAINT test_reject_admin CHECK (member_role <> 'admin')"))
        await session.commit()
        with pytest.raises(IntegrityError):
            await add_group(session, owner)
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(Group)) == 0
        assert await session.scalar(select(func.count()).select_from(Membership)) == 0


@pytest.mark.asyncio
async def test_duplicate_memberships_are_rejected_by_repository_and_database(sessions):
    from sqlalchemy import func
    from sqlalchemy.exc import IntegrityError
    from app.domains.study_groups.domain.exceptions import StudyGroupAlreadyMemberError
    from app.models.orm_models import Membership, MemberRole
    async with sessions() as session:
        owner = await add_user(session)
        member = await add_user(session, email="second@example.com")
        group = await add_group(session, owner)
        repo = PostgreSQLStudyGroupRepository(session)
        await add_membership(repo, group, member)
        with pytest.raises(StudyGroupAlreadyMemberError):
            await add_membership(repo, group, member)
        await session.rollback()
        session.add(Membership(group_id=UUID(group.group.group_id), user_id=member.user_id,
            member_role=MemberRole.MEMBER, joined_at=datetime.now(timezone.utc)))
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()
        assert await session.scalar(select(func.count()).select_from(Membership).where(
            Membership.group_id == UUID(group.group.group_id), Membership.user_id == member.user_id)) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("same_user", [False, True], ids=["last-capacity-slot", "same-member"])
async def test_concurrent_memberships_cannot_exceed_capacity_or_duplicate_a_user(sessions, same_user):
    import asyncio
    from app.domains.study_groups.domain.exceptions import StudyGroupAlreadyMemberError, StudyGroupFullError
    async with sessions() as session:
        owner = await add_user(session)
        first = await add_user(session, email="first@example.com")
        second = first if same_user else await add_user(session, email="second@example.com")
        group = await add_group(session, owner, max_members=3 if same_user else 2)

    async def join(user):
        async with sessions() as session:
            return await add_membership(PostgreSQLStudyGroupRepository(session), group, user)

    results = await asyncio.wait_for(asyncio.gather(join(first), join(second), return_exceptions=True), timeout=15)
    expected_error = StudyGroupAlreadyMemberError if same_user else StudyGroupFullError
    assert sum(isinstance(result, expected_error) for result in results) == 1
    assert sum(not isinstance(result, BaseException) for result in results) == 1
    async with sessions() as session:
        assert await PostgreSQLStudyGroupRepository(session).count_members(group_id=group.group.group_id) == 2


@pytest.mark.asyncio
async def test_capacity_counts_owner_and_releases_a_slot_after_leave(sessions):
    from app.domains.study_groups.application.services import StudyGroupService
    from app.domains.study_groups.domain.exceptions import StudyGroupFullError
    from app.models.orm_models import Membership
    async with sessions() as session:
        owner = await add_user(session)
        first = await add_user(session, email="first@example.com")
        second = await add_user(session, email="second@example.com")
        group = await add_group(session, owner, max_members=2)
        repo = PostgreSQLStudyGroupRepository(session)
        service = StudyGroupService(repo)
        await service.join_public_group(group_id=group.group.group_id, user_id=str(first.user_id))
        membership = await repo.get_membership(group_id=group.group.group_id, user_id=str(first.user_id))
        with pytest.raises(StudyGroupFullError):
            await add_membership(repo, group, second)
        await session.rollback()
        await service.leave_group(group_id=group.group.group_id, user_id=str(first.user_id))
        assert await session.get(Membership, membership.membership_id) is None
        await service.join_public_group(group_id=group.group.group_id, user_id=str(second.user_id))
        assert await repo.count_members(group_id=group.group.group_id) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("manager_role", ["owner", "admin"])
async def test_owner_or_admin_can_add_and_remove_members_but_ordinary_members_cannot(sessions, manager_role):
    from app.domains.study_groups.application.services import StudyGroupService
    from app.domains.study_groups.domain.exceptions import StudyGroupPermissionDeniedError, StudyGroupTargetUserNotFoundError
    from app.models.orm_models import Membership
    async with sessions() as session:
        owner = await add_user(session)
        admin = await add_user(session, email="admin@example.com")
        ordinary = await add_user(session, email="ordinary@example.com")
        target = await add_user(session, email="target@example.com")
        await add_user(session, email="deleted@example.com", deleted=True)
        await add_user(session, email="disabled@example.com", status=ActivityStatus.DEACTIVATED)
        group = await add_group(session, owner, visibility=StudyGroupVisibility.PRIVATE)
        repo = PostgreSQLStudyGroupRepository(session)
        service = StudyGroupService(repo)
        await add_membership(repo, group, admin, role=StudyGroupMemberRole.ADMIN)
        await add_membership(repo, group, ordinary)
        manager = owner if manager_role == "owner" else admin
        scope = dict(group_id=group.group.group_id, requester_user_id=str(manager.user_id))
        with pytest.raises(StudyGroupPermissionDeniedError):
            await service.add_member_by_email(group_id=group.group.group_id,
                requester_user_id=str(ordinary.user_id), email="target@example.com")
        for email in ("deleted@example.com", "disabled@example.com"):
            with pytest.raises(StudyGroupTargetUserNotFoundError):
                await service.add_member_by_email(**scope, email=email)
        added = await service.add_member_by_email(**scope, email=" TARGET@EXAMPLE.COM ")
        assert added.user_id == str(target.user_id) and added.role == StudyGroupMemberRole.MEMBER
        with pytest.raises(StudyGroupPermissionDeniedError):
            await service.remove_member(group_id=group.group.group_id,
                requester_user_id=str(ordinary.user_id), target_user_id=str(target.user_id))
        for protected in (owner, admin):
            with pytest.raises(StudyGroupPermissionDeniedError):
                await service.remove_member(**scope, target_user_id=str(protected.user_id))
        await service.remove_member(**scope, target_user_id=str(target.user_id))
        assert await session.get(Membership, added.membership_id) is None
        assert await repo.get_membership(group_id=group.group.group_id, user_id=str(target.user_id)) is None
        assert not await repo.delete_membership(group_id=group.group.group_id, user_id=str(target.user_id))
        assert await repo.count_members(group_id=group.group.group_id) == 3


@pytest.mark.asyncio
async def test_only_message_author_can_edit_or_delete_even_when_requester_is_owner_or_admin(sessions):
    from app.domains.study_groups.application.services import StudyGroupService
    from app.domains.study_groups.domain.exceptions import StudyGroupMessagePermissionDeniedError, StudyGroupMessageNotFoundError
    from app.models.orm_models import Message
    async with sessions() as session:
        owner = await add_user(session)
        admin = await add_user(session, email="admin@example.com")
        author = await add_user(session, email="author@example.com")
        member = await add_user(session, email="member2@example.com")
        group = await add_group(session, owner)
        repo = PostgreSQLStudyGroupRepository(session)
        service = StudyGroupService(repo)
        for user, role in ((admin, StudyGroupMemberRole.ADMIN), (author, StudyGroupMemberRole.MEMBER),
                           (member, StudyGroupMemberRole.MEMBER)):
            await add_membership(repo, group, user, role=role)
        channel = await add_channel(repo, group, owner)
        sibling = await add_channel(repo, group, owner, name="Sibling")
        scope = dict(group_id=group.group.group_id, channel_id=channel.channel_id)
        message = await service.create_message(**scope, user_id=str(author.user_id), content="Original")
        for other in (owner, admin, member):
            with pytest.raises(StudyGroupMessagePermissionDeniedError):
                await service.update_message(**scope, message_id=message.message_id,
                    user_id=str(other.user_id), content="Forbidden")
            with pytest.raises(StudyGroupMessagePermissionDeniedError):
                await service.delete_message(**scope, message_id=message.message_id, user_id=str(other.user_id))
        wrong = dict(group_id=group.group.group_id, channel_id=sibling.channel_id,
            message_id=message.message_id, user_id=str(author.user_id))
        with pytest.raises(StudyGroupMessageNotFoundError):
            await service.update_message(**wrong, content="Wrong channel")
        with pytest.raises(StudyGroupMessageNotFoundError):
            await service.delete_message(**wrong)
        assert (await repo.get_message(**scope, message_id=message.message_id)).content == "Original"
        updated = await service.update_message(**scope, message_id=message.message_id,
            user_id=str(author.user_id), content="Author edit")
        assert updated.content == "Author edit" and updated.edited_at is not None
        await service.delete_message(**scope, message_id=message.message_id, user_id=str(author.user_id))
        assert (await session.get(Message, message.message_id)).deleted_at is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("deleted_parent", ["group", "channel", "message"])
async def test_deleted_group_channel_or_message_hides_history_and_rejects_message_writes(sessions, deleted_parent):
    from app.domains.study_groups.domain.exceptions import StudyGroupChannelNotFoundError, StudyGroupMessageNotFoundError
    from app.domains.study_groups.domain.models import StudyGroupAiMode
    async with sessions() as session:
        owner = await add_user(session)
        group = await add_group(session, owner)
        repo = PostgreSQLStudyGroupRepository(session)
        channel = await add_channel(repo, group, owner)
        message = await add_message(repo, group, channel, owner, mode=StudyGroupAiMode.DEFAULT)
        scope = dict(group_id=group.group.group_id, channel_id=channel.channel_id)
        timestamp = datetime.now(timezone.utc)
        if deleted_parent == "group":
            await repo.soft_delete_group(group_id=group.group.group_id, deleted_at=timestamp)
        elif deleted_parent == "channel":
            await repo.soft_delete_channel(**scope, deleted_at=timestamp)
        else:
            await repo.soft_delete_message(**scope, message_id=message.message_id, deleted_at=timestamp)
    async with sessions() as session:
        repo = PostgreSQLStudyGroupRepository(session)
        assert await repo.get_message(**scope, message_id=message.message_id) is None
        assert await repo.list_messages(**scope, offset=0, limit=10) == ([], 0)
        with pytest.raises(StudyGroupMessageNotFoundError):
            await repo.update_message(**scope, message_id=message.message_id,
                content="Hidden edit", mentioned_user_ids=(), edited_at=timestamp)
        with pytest.raises(StudyGroupMessageNotFoundError):
            await repo.save_ai_response(**scope, message_id=message.message_id,
                mode=StudyGroupAiMode.DEFAULT, content="Hidden answer", sources=(), generated_at=timestamp)
        assert not await repo.soft_delete_message(**scope, message_id=message.message_id, deleted_at=timestamp)
        if deleted_parent in ("group", "channel"):
            assert await repo.get_channel(**scope) is None
            with pytest.raises(StudyGroupChannelNotFoundError):
                await add_message(repo, group, channel, owner)
            with pytest.raises(StudyGroupChannelNotFoundError):
                await repo.update_channel(**scope, name="Hidden", description=None, updated_at=timestamp)
        if deleted_parent == "group":
            assert await repo.get_group(group_id=group.group.group_id) is None
            assert await repo.get_membership(group_id=group.group.group_id, user_id=str(owner.user_id)) is None
            assert await repo.count_members(group_id=group.group.group_id) == 0
            with pytest.raises(StudyGroupChannelNotFoundError):
                await add_channel(repo, group, owner)


@pytest.mark.asyncio
async def test_mentions_can_be_cleared_and_changes_survive_a_new_session(sessions):
    from sqlalchemy import func
    from app.models.orm_models import MessageMention
    async with sessions() as session:
        owner = await add_user(session)
        member = await add_user(session, email="mention@example.com")
        group = await add_group(session, owner)
        repo = PostgreSQLStudyGroupRepository(session)
        await add_membership(repo, group, member)
        channel = await add_channel(repo, group, owner)
        message = await add_message(repo, group, channel, owner, mentions=(str(member.user_id),))
        scope = dict(group_id=group.group.group_id, channel_id=channel.channel_id, message_id=message.message_id)
    async with sessions() as session:
        repo = PostgreSQLStudyGroupRepository(session)
        assert (await repo.get_message(**scope)).mentioned_user_ids == (str(member.user_id),)
        await repo.update_message(**scope, content="No mentions", mentioned_user_ids=(), edited_at=datetime.now(timezone.utc))
    async with sessions() as session:
        message = await PostgreSQLStudyGroupRepository(session).get_message(**scope)
        assert message.mentioned_user_ids == () and message.content == "No mentions"
        assert await session.scalar(select(func.count()).select_from(MessageMention)) == 0
