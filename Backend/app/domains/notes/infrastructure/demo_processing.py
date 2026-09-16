"""Temporary synchronous PDF processor for the local integration demo.

This adapter proves the upload-to-Chat handoff without PostgreSQL, pgvector,
Celery, embeddings, or an external model. It extracts selectable PDF text,
creates small in-memory chunks scoped to the uploader, and marks the note
ready. Krish's real pipeline must replace it before staging or production.
"""

import asyncio
from collections.abc import Callable

from app.domains.chats.domain.models import ChatSource
from app.domains.chats.domain.retrieval import GroundingChunk
from app.domains.chats.infrastructure.memory_retrieval import (
    InMemoryReadyNoteChunkRepository,
)
from app.domains.notes.domain.models import NoteProcessingStatus
from app.domains.notes.domain.processing import (
    AttachmentProcessingDispatcher,
)
from app.domains.notes.domain.repository import AttachmentRepository


PageExtractor = Callable[[str], tuple[tuple[int, str], ...]]


class SynchronousDemoAttachmentProcessingDispatcher(
    AttachmentProcessingDispatcher
):
    """Extract text and seed authorized chunks during the upload request."""

    def __init__(
        self,
        *,
        attachment_repository: AttachmentRepository,
        chunk_repository: InMemoryReadyNoteChunkRepository,
        page_extractor: PageExtractor | None = None,
        chunk_size_words: int = 220,
        overlap_words: int = 40,
    ) -> None:
        """Initialize the local-only processing bridge."""

        if chunk_size_words <= 0:
            raise ValueError("chunk_size_words must be positive")
        if overlap_words < 0 or overlap_words >= chunk_size_words:
            raise ValueError(
                "overlap_words must be non-negative and smaller than the chunk"
            )

        self._attachment_repository = attachment_repository
        self._chunk_repository = chunk_repository
        self._page_extractor = page_extractor or extract_pdf_text_pages
        self._chunk_size_words = chunk_size_words
        self._overlap_words = overlap_words

    async def dispatch(
        self,
        *,
        attachment_id: int,
        object_path: str,
    ) -> None:
        """Process one uploaded PDF immediately for a local demonstration.

        Failures are stored on the attachment rather than re-raised because
        file storage and initial metadata creation have already succeeded.
        """

        attachment = await self._attachment_repository.get_attachment_by_id(
            attachment_id
        )
        if attachment is None:
            raise ValueError("attachment does not exist")

        await self._attachment_repository.update_processing_status(
            attachment_id=attachment_id,
            processing_status=NoteProcessingStatus.PROCESSING,
            processing_progress=10,
        )

        try:
            pages = await asyncio.to_thread(
                self._page_extractor,
                object_path,
            )
            chunks = self._build_chunks(
                attachment_id=attachment_id,
                title=attachment.title,
                pages=pages,
            )

            if not chunks:
                raise ValueError("the PDF contains no selectable text")

            await self._chunk_repository.replace_attachment_chunks(
                user_id=attachment.uploaded_by,
                note_id=attachment_id,
                chunks=chunks,
            )
            await self._attachment_repository.update_processing_status(
                attachment_id=attachment_id,
                processing_status=NoteProcessingStatus.READY,
                processing_progress=100,
            )
        except Exception:
            await self._attachment_repository.update_processing_status(
                attachment_id=attachment_id,
                processing_status=NoteProcessingStatus.FAILED,
                processing_progress=10,
                processing_error=(
                    "The temporary local processor could not extract text "
                    "from this PDF."
                ),
            )

    def _build_chunks(
        self,
        *,
        attachment_id: int,
        title: str,
        pages: tuple[tuple[int, str], ...],
    ) -> tuple[GroundingChunk, ...]:
        """Split extracted pages into stable, source-bearing local chunks."""

        result: list[GroundingChunk] = []
        sequence = 1
        step = self._chunk_size_words - self._overlap_words

        for page_number, text in pages:
            words = text.split()

            for start in range(0, len(words), step):
                content = " ".join(
                    words[start : start + self._chunk_size_words]
                ).strip()
                if not content:
                    continue

                # The temporary identifier is unique across local attachments.
                chunk_id = attachment_id * 1_000_000 + sequence
                result.append(
                    GroundingChunk(
                        content=content,
                        source=ChatSource(
                            note_id=attachment_id,
                            note_title=title,
                            chunk_id=chunk_id,
                            page=page_number,
                        ),
                    )
                )
                sequence += 1

                if start + self._chunk_size_words >= len(words):
                    break

        return tuple(result)


def extract_pdf_text_pages(
    object_path: str,
) -> tuple[tuple[int, str], ...]:
    """Extract selectable text with PyMuPDF without model/API calls.

    Image captioning, OCR, safety classification, embeddings, and semantic
    retrieval deliberately remain outside this temporary adapter.
    """

    import pymupdf

    document = pymupdf.open(object_path)
    try:
        pages: list[tuple[int, str]] = []
        for page_index, page in enumerate(document):
            text = page.get_text("text").strip()
            if text:
                pages.append((page_index + 1, text))
        return tuple(pages)
    finally:
        document.close()
