"""Integration coverage for PostgreSQL Notes and personal Chat adapters."""

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domains.auth.infrastructure.repository import (
    PostgreSQLAuthRepository,
)
from app.domains.chats.domain.models import ChatMessageRole
from app.domains.chats.infrastructure.repository import (
    PostgreSQLChatRepository,
)
from app.domains.chats.infrastructure.retrieval import (
    PostgreSQLReadyNoteChunkRepository,
)
from app.domains.notes.domain.models import NoteProcessingStatus
from app.domains.notes.infrastructure.repository import (
    PostgreSQLAttachmentRepository,
)


TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    (
        "postgresql+psycopg://"
        "spc_backend:spc_local_password@postgres:5432/spc_auth_test"
    ),
)


async def clear_domain_tables(engine) -> None:
    """Reset database-owned test records without dropping the schema."""

    async with engine.begin() as connection:
        await connection.execute(
            text(
                """
                TRUNCATE TABLE
                    ai_response_sources,
                    ai_responses,
                    chunks,
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
async def test_note_chunks_and_personal_chat_persist_end_to_end() -> None:
    """Persist a ready note, grounded answer, and readable chat history."""

    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        await clear_domain_tables(engine)

        async with session_factory() as session:
            auth_repository = PostgreSQLAuthRepository(session)
            user = await auth_repository.create_user(
                full_name="Repository Integration Student",
                email="note-chat-integration@example.com",
                hashed_password="integration-password-hash",
            )

        async with session_factory() as session:
            attachment_repository = PostgreSQLAttachmentRepository(session)
            attachment = await attachment_repository.create_attachment(
                uploaded_by=user.id,
                title="Database Systems",
                file_name="database-systems.pdf",
                file_type="application/pdf",
                file_size_bytes=1024,
                object_path="/private/database-systems.pdf",
            )
            await attachment_repository.update_processing_status(
                attachment_id=attachment.attachment_id,
                processing_status=NoteProcessingStatus.READY,
                processing_progress=100,
            )

        async with session_factory() as session:
            chunk_repository = PostgreSQLReadyNoteChunkRepository(session)
            await chunk_repository.replace_embedded_attachment_chunks(
                attachment_id=attachment.attachment_id,
                chunks=[
                    {
                        "chunk_id": 0,
                        "source_page": 1,
                        "source_type": "text",
                        "text": "PostgreSQL is a relational database.",
                        "embedding": [0.0] * 768,
                    }
                ],
            )
            grounding_chunks = (
                await chunk_repository.list_ready_chunks_for_user(
                    user_id=user.id
                )
            )

            assert len(grounding_chunks) == 1
            assert grounding_chunks[0].source.note_title == "Database Systems"

        async with session_factory() as session:
            chat_repository = PostgreSQLChatRepository(session)
            chat = await chat_repository.create_chat(
                owner_id=user.id,
                title="Database Revision",
            )
            duplicate_title_chat = await chat_repository.create_chat(
                owner_id=user.id,
                title="Database Revision",
            )
            assert duplicate_title_chat.title == "Database Revision (2)"

            user_message = await chat_repository.create_message(
                chat_id=chat.chat_id,
                role=ChatMessageRole.USER,
                content="What is PostgreSQL?",
            )
            assistant_message = await chat_repository.create_message(
                chat_id=chat.chat_id,
                role=ChatMessageRole.ASSISTANT,
                content="PostgreSQL is a relational database.",
                sources=(grounding_chunks[0].source,),
            )
            history, total = await chat_repository.list_messages(
                chat_id=chat.chat_id,
                offset=0,
                limit=20,
            )

            assert user_message.message_id > 0
            assert assistant_message.message_id > 0
            assert total == 2
            assert [message.role for message in history] == [
                ChatMessageRole.USER,
                ChatMessageRole.ASSISTANT,
            ]
            assert history[1].sources[0].note_id == attachment.attachment_id

    finally:
        await engine.dispose()
