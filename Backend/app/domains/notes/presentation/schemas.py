"""Public request and response schemas for Notes endpoints."""

from datetime import datetime

from pydantic import BaseModel

from app.domains.notes.domain.models import (
    NoteAttachment,
    NoteProcessingStatus,
)


class NoteResponse(BaseModel):
    """Public note metadata that excludes private storage information."""

    id: int
    title: str
    file_name: str
    content_type: str
    file_size: int
    status: NoteProcessingStatus
    processing_progress: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_attachment(cls, attachment: NoteAttachment) -> "NoteResponse":
        """Create an API response from a private domain object."""

        return cls(
            id=attachment.attachment_id,
            title=attachment.title,
            file_name=attachment.file_name,
            content_type=attachment.file_type,
            file_size=attachment.file_size_bytes,
            status=attachment.processing_status,
            processing_progress=attachment.processing_progress,
            created_at=attachment.uploaded_at,
            updated_at=attachment.updated_at,
        )


class NoteListItemResponse(BaseModel):
    """Compact note metadata displayed in My Notes."""

    id: int
    title: str
    file_name: str
    status: NoteProcessingStatus
    processing_progress: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_attachment(
        cls,
        attachment: NoteAttachment,
    ) -> "NoteListItemResponse":
        """Create a list item from an attachment domain object."""

        return cls(
            id=attachment.attachment_id,
            title=attachment.title,
            file_name=attachment.file_name,
            status=attachment.processing_status,
            processing_progress=attachment.processing_progress,
            created_at=attachment.uploaded_at,
            updated_at=attachment.updated_at,
        )


class NoteListResponse(BaseModel):
    """Paginated response for the authenticated student's notes."""

    items: list[NoteListItemResponse]
    page: int
    page_size: int
    total: int


class ProcessingFailureResponse(BaseModel):
    """Safe processing failure information exposed to the frontend."""

    code: str
    message: str
    retryable: bool = False


class NoteStatusResponse(BaseModel):
    """Current document-processing status for one owned note."""

    note_id: int
    status: NoteProcessingStatus
    progress: int
    message: str
    error: ProcessingFailureResponse | None
    updated_at: datetime

    @classmethod
    def from_attachment(
        cls,
        attachment: NoteAttachment,
    ) -> "NoteStatusResponse":
        """Translate an attachment lifecycle state for polling clients."""

        messages = {
            NoteProcessingStatus.QUEUED: "Note is queued for processing",
            NoteProcessingStatus.PROCESSING: "Processing document",
            NoteProcessingStatus.READY: "Note is ready for questions",
            NoteProcessingStatus.FAILED: "Document processing failed",
        }

        failure = None
        if attachment.processing_status == NoteProcessingStatus.FAILED:
            failure = ProcessingFailureResponse(
                code="DOCUMENT_PROCESSING_FAILED",
                message=(
                    attachment.processing_error
                    or "The document could not be processed."
                ),
            )

        return cls(
            note_id=attachment.attachment_id,
            status=attachment.processing_status,
            progress=attachment.processing_progress,
            message=messages[attachment.processing_status],
            error=failure,
            updated_at=attachment.updated_at,
        )
