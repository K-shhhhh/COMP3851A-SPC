"""Temporary in-memory repository for uploaded learning materials.

This adapter supports local development while the PostgreSQL attachment
repository is being implemented. Its contents disappear whenever the backend
process restarts. Never use it in staging or production.
"""

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from itertools import count

from app.domains.notes.domain.models import (
    NoteAttachment,
    NoteProcessingStatus,
)
from app.domains.notes.domain.repository import AttachmentRepository


class InMemoryAttachmentRepository(AttachmentRepository):
    """Store temporary attachment records inside one Python process."""

    def __init__(self) -> None:
        """Initialize an empty attachment store and identifier sequence."""

        self._attachments: dict[int, NoteAttachment] = {}
        self._identifier_sequence = count(start=1)

        # Protect writes when concurrent requests operate on the repository.
        self._lock = asyncio.Lock()

    async def create_attachment(
        self,
        *,
        uploaded_by: str,
        title: str,
        file_name: str,
        file_type: str,
        file_size_bytes: int,
        object_path: str,
        channel_id: str | None = None,
        message_id: int | None = None,
    ) -> NoteAttachment:
        """Create a queued attachment and assign its identifier.

        Args:
            uploaded_by: Authenticated identifier of the uploader.
            title: User-facing title.
            file_name: Sanitized original filename.
            file_type: Validated MIME type.
            file_size_bytes: Validated uploaded-file size.
            object_path: Private storage path returned by file storage.
            channel_id: Conversation or group-channel identifier.
            message_id: Message containing the attachment.

        Returns:
            The newly created queued attachment.
        """

        async with self._lock:
            attachment_id = next(self._identifier_sequence)
            current_time = datetime.now(timezone.utc)

            attachment = NoteAttachment(
                attachment_id=attachment_id,
                uploaded_by=uploaded_by,
                title=title,
                file_name=file_name,
                file_type=file_type,
                file_size_bytes=file_size_bytes,
                object_path=object_path,
                processing_status=NoteProcessingStatus.QUEUED,
                processing_progress=0,
                uploaded_at=current_time,
                updated_at=current_time,
                channel_id=channel_id,
                message_id=message_id,
                processing_error=None,
                deleted_at=None,
            )

            self._attachments[attachment_id] = attachment
            return attachment

    async def get_attachment_by_id(
        self,
        attachment_id: int,
    ) -> NoteAttachment | None:
        """Return a non-deleted attachment for trusted internal processing.

        Args:
            attachment_id: Database-style attachment identifier.

        Returns:
            The attachment, or ``None`` when missing or deleted.
        """

        async with self._lock:
            attachment = self._attachments.get(attachment_id)

            if attachment is None or attachment.deleted_at is not None:
                return None

            return attachment

    async def get_owned_attachment(
        self,
        *,
        attachment_id: int,
        user_id: str,
    ) -> NoteAttachment | None:
        """Return an attachment only when it belongs to the requesting user.

        This temporary adapter allows uploader-only access. The PostgreSQL
        implementation will additionally support authorized study-group
        members through membership and channel joins.

        Args:
            attachment_id: Requested attachment identifier.
            user_id: Authenticated requesting user.

        Returns:
            The attachment when access is allowed; otherwise ``None``.
        """

        async with self._lock:
            attachment = self._attachments.get(attachment_id)

            if attachment is None:
                return None

            if attachment.deleted_at is not None:
                return None

            # Conservative local rule: only the uploader receives access.
            if attachment.uploaded_by != user_id:
                return None

            return attachment

    async def list_note_library_attachments(
        self,
        *,
        user_id: str,
        offset: int,
        limit: int,
        processing_status: NoteProcessingStatus | None = None,
    ) -> tuple[list[NoteAttachment], int]:
        """List non-deleted My Notes attachments for one student.

        Message attachments are deliberately excluded, even when the same
        student uploaded them.

        Args:
            user_id: Authenticated Notes Library owner.
            offset: Number of matching records to skip.
            limit: Maximum number of records to return.
            processing_status: Optional processing-state filter.

        Returns:
            The requested page and the total number of matching attachments.
        """

        if offset < 0:
            raise ValueError("offset must not be negative")

        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        async with self._lock:
            matching_attachments = [
                attachment
                for attachment in self._attachments.values()
                if attachment.uploaded_by == user_id
                and attachment.channel_id is None
                and attachment.deleted_at is None
                and (
                    processing_status is None
                    or attachment.processing_status == processing_status
                )
            ]

            # Display the newest uploads first in My Notes.
            matching_attachments.sort(
                key=lambda attachment: attachment.uploaded_at,
                reverse=True,
            )

            total = len(matching_attachments)
            page = matching_attachments[offset : offset + limit]

            return page, total

    async def update_processing_status(
        self,
        *,
        attachment_id: int,
        processing_status: NoteProcessingStatus,
        processing_progress: int,
        processing_error: str | None = None,
    ) -> NoteAttachment | None:
        """Update processing state for a trusted background worker.

        Args:
            attachment_id: Attachment being processed.
            processing_status: New processing lifecycle state.
            processing_progress: Completion percentage.
            processing_error: Safe error message for failed processing.

        Returns:
            The updated attachment, or ``None`` if it is missing or deleted.
        """

        async with self._lock:
            attachment = self._attachments.get(attachment_id)

            if attachment is None or attachment.deleted_at is not None:
                return None

            updated_attachment = replace(
                attachment,
                processing_status=processing_status,
                processing_progress=processing_progress,
                processing_error=processing_error,
                updated_at=datetime.now(timezone.utc),
            )

            self._attachments[attachment_id] = updated_attachment
            return updated_attachment

    async def soft_delete_owned_attachment(
        self,
        *,
        attachment_id: int,
        user_id: str,
        deleted_at: datetime,
    ) -> bool:
        """Soft-delete an attachment owned by the requesting user.

        Args:
            attachment_id: Attachment requested for deletion.
            user_id: Authenticated requesting user.
            deleted_at: Deletion timestamp.

        Returns:
            ``True`` when deletion succeeds; otherwise ``False``.
        """

        async with self._lock:
            attachment = self._attachments.get(attachment_id)

            if attachment is None:
                return False

            if attachment.deleted_at is not None:
                return False

            if attachment.uploaded_by != user_id:
                return False

            deleted_attachment = replace(
                attachment,
                deleted_at=deleted_at,
                updated_at=deleted_at,
            )

            self._attachments[attachment_id] = deleted_attachment
            return True
