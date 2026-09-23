"""The real background processing task, run by the worker container.

This is where extract -> chunk -> embed -> publish actually happens now,
moved out of the synchronous request path. Runs in a separate process from
the API (the worker container), so it constructs its own repository
instances pointed at the same Redis, rather than sharing anything from the
API process's memory.
"""

import asyncio
import logging
import os

from redis.asyncio import Redis

from app.workers.celery_app import celery_app
from app.domains.notes.domain.models import NoteProcessingStatus
from app.domains.notes.infrastructure.redis_repository import (
    RedisAttachmentRepository,
)
from app.domains.chats.infrastructure.redis_retrieval import (
    RedisReadyNoteChunkRepository,
)
from app.domains.chats.domain.retrieval import GroundingChunk
from app.domains.chats.domain.models import ChatSource

from app.ai.rag.parser import extract_structured_pdf
from app.ai.rag.chunking import chunk_documents
from app.ai.rag.embedding import embed_chunks

logger = logging.getLogger(__name__)


def _build_repositories() -> tuple[RedisAttachmentRepository, RedisReadyNoteChunkRepository]:
    """Construct this process's own Redis client and repositories.

    Called fresh inside the task rather than at import time, since the
    worker process needs its own connection, not one inherited from
    somewhere else.
    """

    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    redis_client = Redis.from_url(redis_url, decode_responses=True)

    attachment_repository = RedisAttachmentRepository(redis_client)
    chunk_repository = RedisReadyNoteChunkRepository(redis_client)

    return attachment_repository, chunk_repository


@celery_app.task(name="spc.process_attachment")
def process_attachment_task(attachment_id: int, object_path: str) -> None:
    """Celery entry point -- Celery tasks are plain synchronous functions,
    but our repositories and toolkit calls are async, so this wraps the
    real work in asyncio.run() to actually execute them."""

    asyncio.run(_process_attachment_async(attachment_id, object_path))


async def _process_attachment_async(attachment_id: int, object_path: str) -> None:
    """The actual processing logic, same shape as the old synchronous
    dispatcher, just running inside the worker process now instead of
    inline during the upload request."""

    attachment_repository, chunk_repository = _build_repositories()

    await attachment_repository.update_processing_status(
        attachment_id=attachment_id,
        processing_status=NoteProcessingStatus.PROCESSING,
        processing_progress=1,
    )

    try:
        pages = extract_structured_pdf(object_path, image_mode="strict")
        chunks = chunk_documents(pages, chunk_size_words=350, overlap_words=60)
        embedded_chunks = embed_chunks(chunks, attachment_id)

        attachment = await attachment_repository.get_attachment_by_id(attachment_id)
        if attachment is None:
            raise ValueError(f"attachment {attachment_id} not found after processing")

        grounding_chunks = []
        for chunk in embedded_chunks:
            source = ChatSource(
                note_id=attachment_id,
                note_title=attachment.title,
                chunk_id=chunk["chunk_id"] + 1,  # ChatSource requires chunk_id > 0; ours starts at 0
                page=chunk.get("source_page"),
            )
            grounding_chunks.append(GroundingChunk(content=chunk["text"], source=source))

        await chunk_repository.replace_attachment_chunks(
            user_id=attachment.uploaded_by,
            note_id=attachment_id,
            chunks=tuple(grounding_chunks),
        )

        await attachment_repository.update_processing_status(
            attachment_id=attachment_id,
            processing_status=NoteProcessingStatus.READY,
            processing_progress=100,
        )

    except Exception as error:
        # Log the full error to the worker's own console output -- without
        # this, a failure is only visible by manually reading Redis, exactly
        # the same silent-catch problem we already hit once in
        # rag_processing.py before Celery existed.
        logger.exception(f"Processing failed for attachment {attachment_id}")

        await attachment_repository.update_processing_status(
            attachment_id=attachment_id,
            processing_status=NoteProcessingStatus.FAILED,
            processing_progress=0,
            processing_error=str(error)[:500],
        )
