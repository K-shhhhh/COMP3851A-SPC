"""The real background processing task, run by the worker container.

This is where extract -> chunk -> embed -> persist happens, outside the API
request. The worker creates its own PostgreSQL session because it runs in a
separate process from FastAPI.
"""

import asyncio
import logging

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import _async_database_url
from app.workers.celery_app import celery_app
from app.domains.notes.domain.models import NoteProcessingStatus
from app.domains.notes.infrastructure.repository import (
    PostgreSQLAttachmentRepository,
)
from app.domains.chats.infrastructure.retrieval import (
    PostgreSQLReadyNoteChunkRepository,
)

from app.ai.rag.parser import extract_structured_pdf
from app.ai.rag.chunking import chunk_documents
from app.ai.rag.embedding import embed_chunks

logger = logging.getLogger(__name__)


@celery_app.task(name="spc.process_attachment")
def process_attachment_task(attachment_id: int, object_path: str) -> None:
    """Celery entry point -- Celery tasks are plain synchronous functions,
    but our repositories and toolkit calls are async, so this wraps the
    real work in asyncio.run() to actually execute them."""

    asyncio.run(_process_attachment_async(attachment_id, object_path))


async def _process_attachment_async(attachment_id: int, object_path: str) -> None:
    """Process one attachment and persist all state in PostgreSQL."""

    engine = create_async_engine(
        _async_database_url(settings.DATABASE_URL),
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            attachment_repository = PostgreSQLAttachmentRepository(session)
            chunk_repository = PostgreSQLReadyNoteChunkRepository(session)

            await attachment_repository.update_processing_status(
                attachment_id=attachment_id,
                processing_status=NoteProcessingStatus.PROCESSING,
                processing_progress=1,
            )

            try:
                pages = extract_structured_pdf(
                    object_path,
                    image_mode="strict",
                )
                chunks = chunk_documents(
                    pages,
                    chunk_size_words=350,
                    overlap_words=60,
                )
                embedded_chunks = embed_chunks(chunks, attachment_id)

                await chunk_repository.replace_embedded_attachment_chunks(
                    attachment_id=attachment_id,
                    chunks=embedded_chunks,
                )

                await attachment_repository.update_processing_status(
                    attachment_id=attachment_id,
                    processing_status=NoteProcessingStatus.READY,
                    processing_progress=100,
                )
            except Exception as error:
                logger.exception(
                    "Processing failed for attachment %s",
                    attachment_id,
                )

                await attachment_repository.update_processing_status(
                    attachment_id=attachment_id,
                    processing_status=NoteProcessingStatus.FAILED,
                    processing_progress=0,
                    processing_error=str(error)[:500],
                )
    finally:
        await engine.dispose()
