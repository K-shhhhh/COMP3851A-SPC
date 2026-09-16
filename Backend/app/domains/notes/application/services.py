"""Application use cases for student learning-material uploads."""

import re
from datetime import datetime, timezone
from pathlib import Path
from unicodedata import normalize

from app.domains.notes.domain.exceptions import (
    AttachmentNotFoundError,
    EmptyFileError,
    FileTooLargeError,
    InvalidPdfError,
    ProcessingDispatchError,
    UnsafeFilenameError,
    UnsupportedFileTypeError,
)
from app.domains.notes.domain.models import (
    NoteAttachment,
    NoteProcessingStatus,
)
from app.domains.notes.domain.processing import (
    AttachmentProcessingDispatcher,
)
from app.domains.notes.domain.repository import AttachmentRepository
from app.domains.notes.domain.storage import AttachmentStorage


class NoteService:
    """Coordinate validation, storage, metadata, and processing handoff."""

    def __init__(
        self,
        *,
        repository: AttachmentRepository,
        storage: AttachmentStorage,
        processing_dispatcher: AttachmentProcessingDispatcher,
        maximum_file_size_bytes: int,
    ) -> None:
        """Initialize the service with infrastructure abstractions."""

        if maximum_file_size_bytes <= 0:
            raise ValueError("maximum_file_size_bytes must be positive")

        self._repository = repository
        self._storage = storage
        self._processing_dispatcher = processing_dispatcher
        self._maximum_file_size_bytes = maximum_file_size_bytes

    async def upload_note(
        self,
        *,
        user_id: str,
        original_filename: str | None,
        content_type: str | None,
        data: bytes,
        title: str | None = None,
    ) -> NoteAttachment:
        """Create a Notes Library attachment and request processing.

        Ownership always comes from the authenticated user. This use case does
        not accept ``channel_id`` because ``/notes/upload`` creates My Notes
        entries only. Message attachments belong to the chat API.
        """

        self._validate_pdf(content_type=content_type, data=data)
        safe_filename = self._sanitize_filename(original_filename)
        safe_title = self._normalize_title(title, safe_filename)

        object_path = await self._storage.store_pdf(data)

        try:
            attachment = await self._repository.create_attachment(
                uploaded_by=user_id,
                title=safe_title,
                file_name=safe_filename,
                file_type="application/pdf",
                file_size_bytes=len(data),
                object_path=object_path,
                channel_id=None,
                message_id=None,
            )
        except Exception:
            await self._storage.delete_pdf(object_path)
            raise

        try:
            await self._processing_dispatcher.dispatch(
                attachment_id=attachment.attachment_id,
                object_path=attachment.object_path,
            )
        except Exception as exc:
            await self._repository.update_processing_status(
                attachment_id=attachment.attachment_id,
                processing_status=NoteProcessingStatus.FAILED,
                processing_progress=0,
                processing_error="Document processing could not be started.",
            )
            raise ProcessingDispatchError(
                "Document processing could not be started."
            ) from exc

        # A normal Celery dispatcher returns while the attachment is queued.
        # The temporary demo dispatcher completes synchronously, so reload the
        # record to return its actual ready/failed state when available.
        current_attachment = await self._repository.get_attachment_by_id(
            attachment.attachment_id
        )
        return current_attachment or attachment

    async def list_notes(
        self,
        *,
        user_id: str,
        page: int,
        page_size: int,
        processing_status: NoteProcessingStatus | None = None,
    ) -> tuple[list[NoteAttachment], int]:
        """List one authenticated student's Notes Library uploads."""

        offset = (page - 1) * page_size
        return await self._repository.list_note_library_attachments(
            user_id=user_id,
            offset=offset,
            limit=page_size,
            processing_status=processing_status,
        )

    async def get_note(
        self,
        *,
        attachment_id: int,
        user_id: str,
    ) -> NoteAttachment:
        """Return an owned Notes Library attachment without exposing paths."""

        attachment = await self._repository.get_owned_attachment(
            attachment_id=attachment_id,
            user_id=user_id,
        )

        if attachment is None or not attachment.appears_in_my_notes:
            raise AttachmentNotFoundError("Note not found.")

        return attachment

    async def delete_note(
        self,
        *,
        attachment_id: int,
        user_id: str,
    ) -> None:
        """Soft-delete owned metadata and remove its original PDF."""

        attachment = await self.get_note(
            attachment_id=attachment_id,
            user_id=user_id,
        )

        deleted = await self._repository.soft_delete_owned_attachment(
            attachment_id=attachment_id,
            user_id=user_id,
            deleted_at=datetime.now(timezone.utc),
        )

        if not deleted:
            raise AttachmentNotFoundError("Note not found.")

        await self._storage.delete_pdf(attachment.object_path)

    def _validate_pdf(
        self,
        *,
        content_type: str | None,
        data: bytes,
    ) -> None:
        """Validate MIME type, size, emptiness, and PDF signature."""

        normalized_type = (content_type or "").split(";", maxsplit=1)[0]
        normalized_type = normalized_type.strip().lower()

        if normalized_type != "application/pdf":
            raise UnsupportedFileTypeError(content_type)

        if not data:
            raise EmptyFileError("The uploaded file is empty.")

        if len(data) > self._maximum_file_size_bytes:
            raise FileTooLargeError(
                actual_size_bytes=len(data),
                maximum_size_bytes=self._maximum_file_size_bytes,
            )

        # The PDF header should occur within the first 1,024 bytes.
        if b"%PDF-" not in data[:1024]:
            raise InvalidPdfError(
                "The uploaded content does not appear to be a valid PDF."
            )

    @staticmethod
    def _sanitize_filename(original_filename: str | None) -> str:
        """Produce a safe display filename without using it as a path."""

        if original_filename is None:
            raise UnsafeFilenameError("A filename is required.")

        candidate = normalize("NFKC", original_filename).strip()

        if (
            not candidate
            or "\x00" in candidate
            or "/" in candidate
            or "\\" in candidate
        ):
            raise UnsafeFilenameError("The uploaded filename is invalid.")

        # Keep readable characters while removing filesystem-sensitive ones.
        safe_name = re.sub(r"[^\w.()\- ]", "_", candidate).strip(" .")
        safe_name = re.sub(r"\s+", " ", safe_name)

        if not safe_name or Path(safe_name).suffix.lower() != ".pdf":
            raise UnsupportedFileTypeError(None)

        if len(safe_name) > 255:
            stem = Path(safe_name).stem[:251].rstrip(" .")
            safe_name = f"{stem}.pdf"

        return safe_name

    @staticmethod
    def _normalize_title(title: str | None, filename: str) -> str:
        """Return a trimmed title or default to the filename stem."""

        normalized_title = (title or Path(filename).stem).strip()

        if not normalized_title:
            normalized_title = "Untitled note"

        return normalized_title[:150]
