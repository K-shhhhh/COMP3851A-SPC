"""Persistence contracts for the Notes domain.

Application services depend on these abstract contracts rather than directly
using PostgreSQL or writing SQL. The database developer implements the contracts
inside the Notes infrastructure layer.
"""

from abc import ABC, abstractmethod
from datetime import datetime

from app.domains.notes.domain.models import (
    NoteAttachment,
    NoteProcessingStatus,
)

class AttachmentRepository(ABC):
    """Define persistence operations for uploaded attachments.

    Public endpoint operations use ownership-aware methods. Background workers
    may use internal methods after receiving a trusted attachment identifier.
    """

    @abstractmethod
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
        """Create an attachement before background processing begins.

        The implementation must create the record with:

            processing_status = queued
            processing_progress = 0

        Args:
            uploaded_by: Authenticated identifier of the uploader.
            title: User-facing attachment title.
            file_name: Sanititzed original filename.
            file_type: Validated MIME type.
            file_size_bytes: Validated file size.
            object_path: Private location of the stored file.
            channel_id: Conversation or group-channel identifier.
            message_id: Message containing the attachment.

        Returns:
            The newly persisted attachment with its generated identifier.
        """

        raise NotImplementedError

    @abstractmethod
    async def get_attachment_by_id(
        self,
        attachment_id: int,
    ) -> NoteAttachment | None:
        """Return an attachment for trusted internal processing.

        This method does not perform user authorization. It is intended for
        internal workers that receive a trusted attachment identifier.

        Args:
            attachment_id: Database attachment identifier.

        Returns:
            The attachment, or ``None`` when it does not exists.
        """

        raise NotImplementedError


    @abstractmethod
    async def get_owned_attachment(
        self,
        *,
        attachment_id: int,
        user_id: str,
    ) -> NoteAttachment | None:
        """Return an attachment only when the user may access it.

        For a Notes Library upload, the user must be the uploader. Message attachments
        also require conversation or study-group authorization.

        Implementations should return ``None`` for both missing and
        unauthorized attachments to prevent resource enumeration.

        Args:
            attachment_id: Requested attachment identifier.
            user_id: Authenticated user identifier.

        Returns:
            The authorized attachment, or ``None``.
        """

        raise NotImplementedError

    @abstractmethod
    async def list_note_library_attachments(
        self,
        *,
        user_id: str,
        offset: int,
        limit: int,
        processing_status: NoteProcessingStatus | None = None,
    ) -> tuple[list[NoteAttachment], int]:
        """List My Notes attachments owned by one student.

        The implementation must include only records where:

            uploaded_by = user_id
            channel_id IS NULL
            deleted_at IS NULL

        Args:
            user_id: Authenticated owner identifier.
            offset: Number of matching records to skip.
            limit: Maximum number of records to return.
            processing_status: Optional processing-state filter.

        Returns:
            A tuple containing the current page and total matching count.
        """

        raise NotImplementedError


    @abstractmethod
    async def update_processing_status(
        self,
        *,
        attachment_id: int,
        processing_status: NoteProcessingStatus,
        processing_progress: int,
        processing_error: str | None = None,
    ) -> NoteAttachment | None:
        """Update attachment processing information for a worker.

        Krish's processing pipeline will use this operation for transitions such as:

            queued -> processing -> ready

        or:

            queued -> processing -> failed

        Args:
            attachment_id: Attachment being processed.
            processing_status: New processing lifecycle state.
            processing_progress: Completion percentage from zero to 100.
            processing_error: Safe failure message for failed processing.

        Returns:
            The updated attachment, or ``None`` if it no longer exists.
        """

        raise NotImplementedError

    @abstractmethod
    async def soft_delete_owned_attachment(
        self,
        *,
        attachment_id: int,
        user_id: str,
        deleted_at: datetime,
    ) -> bool:
        """Soft-delete an attachment that the user is authorized to remove.

        The implementation should set ``deleted_at`` rather than immediately
        deleting the database record or original stored file.

        Args:
            attachment_id: Attachment requested for deletion.
            user_id: Authenticated user requesting deletion.
            deleted_at: Timestamp at which deletion was requested.

        Returns:
            ``True`` when an authorized record was updated; otherwise ``False``.
        """

        raise NotImplementedError
