"""Unit tests for the temporary synchronous note-processing adapter."""

import pytest

from app.domains.chats.infrastructure.memory_retrieval import (
    InMemoryReadyNoteChunkRepository,
)
from app.domains.notes.domain.models import (
    NoteProcessingStatus,
)
from app.domains.notes.infrastructure.demo_processing import (
    SynchronousDemoAttachmentProcessingDispatcher,
)
from app.domains.notes.infrastructure.memory_repository import (
    InMemoryAttachmentRepository,
)


async def _create_attachment(
    repository: InMemoryAttachmentRepository,
):
    """Create a queued attachment through the repository contract."""

    return await repository.create_attachment(
        uploaded_by="student-1",
        title="Bioethanol lecture",
        file_name="bioethanol.pdf",
        file_type="application/pdf",
        file_size_bytes=128,
        object_path="unused-in-injected-test.pdf",
    )


@pytest.mark.asyncio
async def test_demo_processor_marks_note_ready_and_scopes_chunks_to_owner() -> None:
    """Successful processing should create owner-scoped grounding chunks."""

    attachment_repository = InMemoryAttachmentRepository()
    chunk_repository = InMemoryReadyNoteChunkRepository()
    attachment = await _create_attachment(attachment_repository)

    def extract_pages(_object_path: str) -> tuple[tuple[int, str], ...]:
        return (
            (1, "Bioethanol is a renewable fuel produced from plant biomass."),
            (2, "Fermentation converts sugars into ethanol and carbon dioxide."),
        )

    dispatcher = SynchronousDemoAttachmentProcessingDispatcher(
        attachment_repository=attachment_repository,
        chunk_repository=chunk_repository,
        page_extractor=extract_pages,
    )

    await dispatcher.dispatch(
        attachment_id=attachment.attachment_id,
        object_path=attachment.object_path,
    )

    processed = await attachment_repository.get_attachment_by_id(
        attachment.attachment_id
    )
    assert processed is not None
    assert processed.processing_status is NoteProcessingStatus.READY
    assert processed.processing_progress == 100
    assert processed.processing_error is None

    owner_chunks = await chunk_repository.list_ready_chunks_for_user(
        user_id="student-1"
    )
    assert len(owner_chunks) == 2
    assert all(chunk.source.note_id == attachment.attachment_id for chunk in owner_chunks)
    assert all(chunk.source.note_title == attachment.title for chunk in owner_chunks)
    assert await chunk_repository.list_ready_chunks_for_user(
        user_id="student-2"
    ) == ()


@pytest.mark.asyncio
async def test_demo_processor_marks_note_failed_when_extraction_fails() -> None:
    """Extraction failures should be recorded without crashing the upload API."""

    attachment_repository = InMemoryAttachmentRepository()
    chunk_repository = InMemoryReadyNoteChunkRepository()
    attachment = await _create_attachment(attachment_repository)

    def fail_extraction(_object_path: str) -> tuple[tuple[int, str], ...]:
        raise ValueError("Unreadable PDF")

    dispatcher = SynchronousDemoAttachmentProcessingDispatcher(
        attachment_repository=attachment_repository,
        chunk_repository=chunk_repository,
        page_extractor=fail_extraction,
    )

    await dispatcher.dispatch(
        attachment_id=attachment.attachment_id,
        object_path=attachment.object_path,
    )

    processed = await attachment_repository.get_attachment_by_id(
        attachment.attachment_id
    )
    assert processed is not None
    assert processed.processing_status is NoteProcessingStatus.FAILED
    assert processed.processing_progress == 10
    assert processed.processing_error == (
        "The temporary local processor could not extract text from this PDF."
    )
    assert await chunk_repository.list_ready_chunks_for_user(
        user_id="student-1"
    ) == ()
