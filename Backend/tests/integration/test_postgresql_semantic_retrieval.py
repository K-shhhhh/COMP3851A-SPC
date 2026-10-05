"""PostgreSQL permission and ranking checks for pgvector retrieval."""

import os
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domains.chats.infrastructure.retrieval import (
    PostgreSQLReadyNoteChunkRepository,
)
from app.domains.study_groups.infrastructure.retrieval import (
    PostgreSQLStudyGroupReadyChunkRepository,
)


def _vector(first: float, second: float) -> str:
    """Build a valid 768-dimensional pgvector literal."""

    return "[" + ",".join(map(str, (first, second, *([0.0] * 766)))) + "]"


@pytest_asyncio.fixture
async def sessions():
    """Create the current schema in an isolated namespace."""

    url = os.environ.get("SPC_TEST_DATABASE_URL")
    if not url:
        pytest.skip("SPC_TEST_DATABASE_URL is required")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    schema = "spc_semantic_" + uuid4().hex
    admin = create_async_engine(url)
    engine = create_async_engine(
        url,
        connect_args={"options": f"-csearch_path={schema},public"},
    )
    try:
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        schema_sql = (
            Path(__file__).resolve().parents[2]
            / "migrations"
            / "006_create_initial_test_schema.sql"
        ).read_text()
        schema_sql = schema_sql.replace("create extension if not exists vector;", "")
        async with engine.begin() as connection:
            for statement in schema_sql.split(";"):
                if statement.strip():
                    await connection.exec_driver_sql(statement)
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(
                text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            )
        await admin.dispose()


async def _add_user(session, email: str) -> str:
    user_id = str(uuid4())
    await session.execute(
        text(
            """
            INSERT INTO users (
                user_id, email, fullname, password_hash, user_role,
                status, created_at
            ) VALUES (
                CAST(:user_id AS uuid), :email, 'Semantic Test', 'hash',
                'student', 'active', now()
            )
            """
        ),
        {"user_id": user_id, "email": email},
    )
    await session.commit()
    return user_id


async def _add_attachment(
    session,
    *,
    user_id: str,
    title: str,
    show_in_library: bool,
    group_id: str | None = None,
    channel_id: str | None = None,
) -> int:
    attachment_id = await session.scalar(
        text(
            """
            INSERT INTO attachments (
                uploaded_by, group_id, channel_id, title, file_name,
                file_type, file_size_bytes, object_path, processing_status,
                processing_progress, show_in_library, uploaded_at
            ) VALUES (
                CAST(:user_id AS uuid), CAST(:group_id AS uuid),
                CAST(:channel_id AS uuid), :title, :file_name,
                'application/pdf', 10, :object_path, 'ready', 100,
                :show_in_library, now()
            ) RETURNING attachment_id
            """
        ),
        {
            "user_id": user_id,
            "group_id": group_id,
            "channel_id": channel_id,
            "title": title,
            "file_name": f"{title}.pdf",
            "object_path": f"semantic/{title}.pdf",
            "show_in_library": show_in_library,
        },
    )
    await session.commit()
    return int(attachment_id)


async def _add_chunk(
    session,
    *,
    attachment_id: int,
    order: int,
    content: str,
    embedding: str,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO chunks (
                attachment_id, chunk_order, source_page, source_type,
                chunk_content, embedding_model_version, vector_embedding,
                created_at
            ) VALUES (
                :attachment_id, :chunk_order, 1, 'text', :content,
                'nomic-embed-text', CAST(:embedding AS vector), now()
            )
            """
        ),
        {
            "attachment_id": attachment_id,
            "chunk_order": order,
            "content": content,
            "embedding": embedding,
        },
    )
    await session.commit()


@pytest.mark.asyncio
async def test_personal_search_ranks_only_owned_library_chunks(sessions):
    async with sessions() as session:
        owner_id = await _add_user(session, "owner@example.com")
        other_id = await _add_user(session, "other@example.com")
        visible = await _add_attachment(
            session,
            user_id=owner_id,
            title="visible",
            show_in_library=True,
        )
        hidden = await _add_attachment(
            session,
            user_id=owner_id,
            title="hidden",
            show_in_library=False,
        )
        foreign = await _add_attachment(
            session,
            user_id=other_id,
            title="foreign",
            show_in_library=True,
        )
        await _add_chunk(
            session,
            attachment_id=visible,
            order=0,
            content="closest authorized chunk",
            embedding=_vector(1.0, 0.0),
        )
        await _add_chunk(
            session,
            attachment_id=visible,
            order=1,
            content="second authorized chunk",
            embedding=_vector(0.8, 0.2),
        )
        await _add_chunk(
            session,
            attachment_id=hidden,
            order=0,
            content="hidden exact match",
            embedding=_vector(1.0, 0.0),
        )
        await _add_chunk(
            session,
            attachment_id=foreign,
            order=0,
            content="foreign exact match",
            embedding=_vector(1.0, 0.0),
        )

        chunks = await PostgreSQLReadyNoteChunkRepository(
            session
        ).search_ready_chunks_for_user(
            user_id=owner_id,
            query_embedding=(1.0, 0.0, *([0.0] * 766)),
            limit=5,
        )

        assert [chunk.content for chunk in chunks] == [
            "closest authorized chunk",
            "second authorized chunk",
        ]
        assert {chunk.source.note_id for chunk in chunks} == {visible}


@pytest.mark.asyncio
async def test_group_search_never_crosses_channel_scope(sessions):
    async with sessions() as session:
        owner_id = await _add_user(session, "group-owner@example.com")
        group_id = str(uuid4())
        other_group_id = str(uuid4())
        channel_id = str(uuid4())
        other_channel_id = str(uuid4())
        await session.execute(
            text(
                """
                INSERT INTO groups (
                    group_id, group_name, group_type, created_by,
                    current_admin, max_members, created_at
                ) VALUES
                    (CAST(:group_id AS uuid), 'Target', 'public',
                     CAST(:owner_id AS uuid), CAST(:owner_id AS uuid), 20, now()),
                    (CAST(:other_group_id AS uuid), 'Other', 'private',
                     CAST(:owner_id AS uuid), CAST(:owner_id AS uuid), 20, now());
                """
            ),
            {
                "group_id": group_id,
                "other_group_id": other_group_id,
                "owner_id": owner_id,
            },
        )
        await session.execute(
            text(
                """
                INSERT INTO channels (
                    channel_id, channel_name, group_id, created_by, created_at
                ) VALUES
                    (CAST(:channel_id AS uuid), 'Target Channel',
                     CAST(:group_id AS uuid), CAST(:owner_id AS uuid), now()),
                    (CAST(:other_channel_id AS uuid), 'Other Channel',
                     CAST(:other_group_id AS uuid), CAST(:owner_id AS uuid), now());
                """
            ),
            {
                "group_id": group_id,
                "other_group_id": other_group_id,
                "channel_id": channel_id,
                "other_channel_id": other_channel_id,
                "owner_id": owner_id,
            },
        )
        await session.commit()
        target = await _add_attachment(
            session,
            user_id=owner_id,
            title="target",
            show_in_library=False,
            group_id=group_id,
            channel_id=channel_id,
        )
        other = await _add_attachment(
            session,
            user_id=owner_id,
            title="other-channel",
            show_in_library=False,
            group_id=other_group_id,
            channel_id=other_channel_id,
        )
        await _add_chunk(
            session,
            attachment_id=target,
            order=0,
            content="authorized channel chunk",
            embedding=_vector(0.9, 0.1),
        )
        await _add_chunk(
            session,
            attachment_id=other,
            order=0,
            content="other channel exact match",
            embedding=_vector(1.0, 0.0),
        )

        chunks = await PostgreSQLStudyGroupReadyChunkRepository(
            session
        ).search_ready_chunks_for_channel(
            group_id=group_id,
            channel_id=channel_id,
            query_embedding=(1.0, 0.0, *([0.0] * 766)),
            limit=5,
        )

        assert [chunk.content for chunk in chunks] == [
            "authorized channel chunk"
        ]
        assert chunks[0].source.note_id == target
