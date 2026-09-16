"""Domain models for student-uploaded learning notes.

These objects describe uploaded notes independently of FastAPI, PostgreSQL,
file storage, Celery, and the RAG implementation.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class NoteProcessingStatus(StrEnum):
    """Supported lifecycle states for an uploaded learning material."""

    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class NoteAttachment:
    """Represent one uploaded learning-material attachment.

    An attachment with no ``channel_id`` belongs to the uploader's Notes
    Library and appears in My Notes. An attachment with a ``channel_id``
    belongs to a personal conversation or study-group channel and must also
    reference the message through which it was uploaded.

    The group identifier is intentionally not stored on this model. For a
    message attachment, the group can be derived through:

        attachment.channel_id -> channel.group_id

    Attributes:
        attachment_id: Database-generated attachment identifier.
        uploaded_by: Identifier of the student who owns the upload.
        title: User-facing title displayed in My Notes.
        file_name: Sanitized original filename.
        file_type: Validated MIME type, currently ``application/pdf``.
        file_size_bytes: Size of the uploaded file in bytes.
        object_path: Private storage path used by the processing worker.
        processing_status: Current extraction and embedding state.
        processing_progress: Processing percentage between zero and 100.
        uploaded_at: Time at which the attachment was created.
        updated_at: Time at which the attachment was last changed.
        channel_id: Conversation or group-channel identifier, when applicable.
        message_id: Message containing the attachment, when applicable.
        processing_error: Safe error message when processing fails.
        deleted_at: Soft-deletion timestamp, when the attachment is deleted.
    """

    attachment_id: int
    uploaded_by: str
    title: str
    file_name: str
    file_type: str
    file_size_bytes: int
    object_path: str
    processing_status: NoteProcessingStatus
    processing_progress: int
    uploaded_at: datetime
    updated_at: datetime
    channel_id: str | None = None
    message_id: int | None = None
    processing_error: str | None = None
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        """Validate attachment rules shared by every application layer."""

        if self.attachment_id <= 0:
            raise ValueError("attachment_id must be greater than zero")

        if not self.uploaded_by.strip():
            raise ValueError("uploaded_by must not be empty")

        if not self.title.strip():
            raise ValueError("title must not be empty")

        if not self.file_name.strip():
            raise ValueError("file_name must not be empty")

        if self.file_type != "application/pdf":
            raise ValueError(
                "file_type must be application/pdf during this sprint"
            )

        if self.file_size_bytes <= 0:
            raise ValueError("file_size_bytes must be greater than zero")

        if not self.object_path.strip():
            raise ValueError("object_path must not be empty")

        if not 0 <= self.processing_progress <= 100:
            raise ValueError(
                "processing_progress must be between 0 and 100"
            )

        self._validate_attachment_relationships()
        self._validate_processing_state()

    @property
    def appears_in_my_notes(self) -> bool:
        """Return whether this attachment belongs to the Notes Library."""

        return self.channel_id is None

    def _validate_attachment_relationships(self) -> None:
        """Ensure channel and message relationships are unambiguous."""

        if self.channel_id is None and self.message_id is not None:
            raise ValueError(
                "a Notes Library attachment cannot have a message_id"
            )

        if self.channel_id is not None and self.message_id is None:
            raise ValueError(
                "a channel attachment requires a message_id"
            )

    def _validate_processing_state(self) -> None:
        """Ensure processing status, progress, and errors are consistent."""

        if (
            self.processing_status == NoteProcessingStatus.QUEUED
            and self.processing_progress != 0
        ):
            raise ValueError(
                "a queued attachment must have zero processing progress"
            )

        if (
            self.processing_status == NoteProcessingStatus.READY
            and self.processing_progress != 100
        ):
            raise ValueError(
                "a ready attachment must have 100 processing progress"
            )

        if (
            self.processing_status == NoteProcessingStatus.PROCESSING
            and self.processing_progress >= 100
        ):
            raise ValueError(
                "a processing attachment must have progress below 100"
            )

        if (
            self.processing_status == NoteProcessingStatus.FAILED
            and not self.processing_error
        ):
            raise ValueError(
                "a failed attachment must include a processing error"
            )

        if (
            self.processing_status != NoteProcessingStatus.FAILED
            and self.processing_error is not None
        ):
            raise ValueError(
                "only a failed attachment may include a processing error"
            )
