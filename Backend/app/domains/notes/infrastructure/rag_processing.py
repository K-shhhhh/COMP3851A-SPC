"""Integration point for Krish's attachment-processing RAG pipeline.

Krish implements ``AttachmentProcessingDispatcher`` here after exposing the
tested ``process_attachment(attachment_id, object_path)`` function as
importable Python code. Extraction, chunking, embedding, status updates, and
chunk persistence belong to the RAG/background-processing responsibility.

PRAGMATIC DEMO BRIDGE: chat's ChatAnswerGenerator reads chunks from
InMemoryReadyNoteChunkRepository, normally filled by a real PostgreSQL+pgvector
query. Since that repository isn't built yet, this dispatcher pushes chunks
into the SAME shared in-memory chunk repository instance directly, via
replace_attachment_chunks() -- Henrick's helper that replaces only this
attachment's chunks without removing the user's other notes. Once Kaung's
PostgreSQL adapters exist, this goes back to only touching Notes -- the
database does the chunk lookup for chat, not this code.
"""

import asyncio
import logging

from app.domains.notes.domain.processing import AttachmentProcessingDispatcher
from app.domains.notes.domain.repository import AttachmentRepository
from app.domains.notes.domain.models import NoteProcessingStatus

from app.domains.chats.domain.retrieval import GroundingChunk
from app.domains.chats.domain.models import ChatSource
from app.domains.chats.infrastructure.memory_retrieval import (
    InMemoryReadyNoteChunkRepository,
)

from app.ai.rag.parser import extract_structured_pdf
from app.ai.rag.chunking import chunk_documents
from app.ai.rag.embedding import embed_chunks

logger = logging.getLogger(__name__)


class KrishAttachmentProcessingDispatcher(AttachmentProcessingDispatcher):
    """Runs the real pipeline, updates real status, publishes real chunks."""

    def __init__(
        self,
        *,
        attachment_repository: AttachmentRepository,
        chunk_repository: InMemoryReadyNoteChunkRepository,
    ) -> None:
        self._attachment_repository = attachment_repository
        self._chunk_repository = chunk_repository

    async def dispatch(
        self,
        *,
        attachment_id: int,
        object_path: str,
    ) -> None:
        """Request extraction, chunking, and embedding for an attachment."""
        await self._attachment_repository.update_processing_status(
            attachment_id=attachment_id,
            processing_status=NoteProcessingStatus.PROCESSING,
            processing_progress=1,
        )

        try:
            # Only the actual blocking work (PyMuPDF/NudeNet/Ollama/OpenRouter
            # calls) runs on a background thread -- repository calls stay on
            # the event loop, properly awaited.
            embedded_chunks = await asyncio.to_thread(
                self._run_pipeline_sync, object_path, attachment_id
            )

            await self._publish_chunks(attachment_id, embedded_chunks)

            await self._attachment_repository.update_processing_status(
                attachment_id=attachment_id,
                processing_status=NoteProcessingStatus.READY,
                processing_progress=100,
            )

        except Exception as e:
            # Log the FULL error (with traceback) to the console, not just
            # the truncated message stored on the attachment -- this is what
            # was missing before, making failures invisible in `docker compose logs`.
            logger.exception(f"Processing failed for attachment {attachment_id}")

            await self._attachment_repository.update_processing_status(
                attachment_id=attachment_id,
                processing_status=NoteProcessingStatus.FAILED,
                processing_progress=0,
                processing_error=str(e)[:500],
            )

    def _run_pipeline_sync(self, object_path: str, attachment_id: int) -> list[dict]:
        """The actual blocking pipeline -- runs inside asyncio.to_thread()."""
        pages = extract_structured_pdf(object_path, image_mode="strict")
        chunks = chunk_documents(pages, chunk_size_words=350, overlap_words=60)
        return embed_chunks(chunks, attachment_id)

    async def _publish_chunks(self, attachment_id: int, embedded_chunks: list[dict]) -> None:
        """Convert embedded chunks into GroundingChunks and publish them for
        this one attachment, without disturbing the user's other notes."""
        attachment = await self._attachment_repository.get_attachment_by_id(attachment_id)
        if attachment is None:
            raise ValueError(f"attachment {attachment_id} not found after processing")

        grounding_chunks = tuple(
            GroundingChunk(
                content=c["text"],
                source=ChatSource(
                    note_id=attachment_id,
                    note_title=attachment.title,
                    chunk_id=c["chunk_id"] + 1,  # ChatSource requires chunk_id > 0; ours starts at 0
                    page=c.get("source_page"),
                ),
            )
            for c in embedded_chunks
        )

        await self._chunk_repository.replace_attachment_chunks(
            user_id=attachment.uploaded_by,
            note_id=attachment_id,
            chunks=grounding_chunks,
        )