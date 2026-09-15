"""Domain and application errors for uploaded learning materials.

These exceptions describe expected Notes-module failures without depending on
FastAPI or HTTP status codes. The presentation layer converts them into the
shared public API error format.
"""

from app.domains.notes.domain.models import NoteProcessingStatus

class NotesError(Exception):
    """Base exception for expected Notes-module failures."""

class AttachmentNotFoundError(NotesError):
    """Raised when an attachment does not exist or is inaccessible."""

class UnsupportedFileTypeError(NotesError):
    """Raised when an uploaded file type is not supported."""

    def __init__(self, received_type: str | None) -> None:
        """Record the rejected content type.

        Args:
            received_type: MINE type received from the uploaded file.
        """

        self.received_type = received_type
        super().__init__("Only PDF files are supported during this sprint.")


class InvalidPdfError(NotesError):
    """Raised when uploaded content does not contain a PDF signature."""


class EmptyFileError(NotesError):
    """Raised when an uploaded file contains no data."""


class FileTooLargeError(NotesError):
    """Raised when an uploaded file exceeds the configured size limit."""

    def __init__(
        self,
        *,
        actual_size_bytes: int,
        maximum_size_bytes: int,
    ) -> None:
        """Record the actual and permitted file sizes.

        Args:
            actual_size_bytes: Number of bytes received from the upload.
            maximum_size_bytes: Maximum permitted upload size.
        """

        self.actual_size_bytes = actual_size_bytes
        self.maximum_size_bytes = maximum_size_bytes

        super().__init__(
            "The uploaded file exceeds the configured size limit."
        )


class UnsafeFilenameError(NotesError):
    """Raised when a safe storage filename connot be produced."""

class AttachmentStorageError(NotesError):
    """Raised when the original file cannot be stored safely."""

class AttachmentNotReadyError(NotesError):
    """Raised when an operation requires a fully processed attachment."""

    def __init__(
        self,
        current_status: NoteProcessingStatus,
    ) -> None:
        """Record the attachment status that prevented the operation.

        Args:
            current_status: Current document-processing lifecycle state.
        """

        self.current_status = current_status

        super().__init__(
            f"The attachment is not ready. Current status: "
            f"{current_status.value}."
        )

class ProcessingDispatchError(NotesError):
    """Raised when the attachment_processing job cannot be queued."""
