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
from app.domains.knowledge_graph.application.services import KnowledgeGraphService
from app.domains.knowledge_graph.infrastructure.repository import (
    PostgreSQLKnowledgeGraphRepository,
)
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
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _generate_graph_sync(
    attachment_id: int,
    chunks: list[dict],
) -> tuple[list, list]:
    """Generate graph data without loading the model client at worker startup.

    The lazy import lets ordinary note processing run when the optional graph
    feature is disabled or its model configuration is not present.
    """

    from app.domains.knowledge_graph.application.graph_generation import (
        generate_graph_for_attachment,
    )

    return generate_graph_for_attachment(attachment_id, chunks)


async def _generate_and_store_graph(
    *,
    attachment_id: int,
    chunks: list[dict],
    graph_service: KnowledgeGraphService,
) -> None:
    """Generate a graph off the event loop and hand it to persistence."""

    nodes, edges = await asyncio.to_thread(
        _generate_graph_sync,
        attachment_id,
        chunks,
    )
    await graph_service.replace_graph_for_attachment(
        attachment_id=attachment_id,
        nodes=nodes,
        edges=edges,
    )


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
            graph_service = None
            if settings.ENABLE_KNOWLEDGE_GRAPH_GENERATION:
                graph_service = KnowledgeGraphService(
                    repository=PostgreSQLKnowledgeGraphRepository(session),
                    attachment_repository=attachment_repository,
                )

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

                if graph_service is not None:
                    await attachment_repository.update_processing_status(
                        attachment_id=attachment_id,
                        processing_status=NoteProcessingStatus.PROCESSING,
                        processing_progress=85,
                    )
                    try:
                        await _generate_and_store_graph(
                            attachment_id=attachment_id,
                            chunks=chunks,
                            graph_service=graph_service,
                        )
                    except Exception:
                        # Graphs are an optional derived view. Preserve the
                        # successfully processed note and chunks for normal RAG.
                        logger.exception(
                            "Knowledge graph generation failed for attachment %s; "
                            "continuing note processing",
                            attachment_id,
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
