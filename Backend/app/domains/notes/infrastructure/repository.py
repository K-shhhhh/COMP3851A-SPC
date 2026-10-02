"""PostgreSQL persistence for uploaded note metadata."""

import uuid
from dataclasses import replace
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.notes.domain.models import NoteAttachment, NoteProcessingStatus
from app.domains.notes.domain.repository import AttachmentRepository
from app.models.orm_models import (
    Attachment as ORMAttachment,
    AttachmentStatus,
    Channel,
    Group,
    GroupType,
    Membership,
    Message,
)


class PostgreSQLAttachmentRepository(AttachmentRepository):
    """Store attachment metadata using a request-scoped SQLAlchemy session."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _parse_uuid(value: str) -> uuid.UUID | None:
        """Parse a public string UUID without leaking conversion errors."""

        try:
            return uuid.UUID(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_domain(attachment: ORMAttachment) -> NoteAttachment:
        """Convert an ORM attachment into the Notes domain model."""

        if attachment.object_path is None:
            raise ValueError("persisted attachment is missing object_path")
        return NoteAttachment(
            attachment_id=attachment.attachment_id,
            uploaded_by=str(attachment.uploaded_by),
            title=attachment.title,
            file_name=attachment.file_name,
            file_type=attachment.file_type,
            file_size_bytes=attachment.file_size_bytes,
            object_path=attachment.object_path,
            processing_status=NoteProcessingStatus(
                attachment.processing_status.value
            ),
            processing_progress=attachment.processing_progress,
            uploaded_at=attachment.uploaded_at,
            updated_at=attachment.last_updated_at or attachment.uploaded_at,
            show_in_library=attachment.show_in_library,
            channel_id=(
                str(attachment.channel_id)
                if attachment.channel_id is not None
                else None
            ),
            message_id=attachment.message_id,
            processing_error=attachment.processing_error,
            deleted_at=attachment.deleted_at,
        )

    async def create_attachment(
        self,
        *,
        uploaded_by: str,
        title: str,
        file_name: str,
        file_type: str,
        file_size_bytes: int,
        object_path: str,
        show_in_library: bool = True,
        channel_id: str | None = None,
        message_id: int | None = None,
    ) -> NoteAttachment:
        """Create metadata with visibility derived from the stored group type.

        The visibility argument is retained for the shared repository interface;
        PostgreSQL derives the authoritative value from the upload destination.
        """

        uploader_uuid = self._parse_uuid(uploaded_by)
        if uploader_uuid is None:
            raise ValueError("uploaded_by must be a valid UUID")
        if message_id is not None and channel_id is None:
            raise ValueError("message_id requires a channel_id")

        channel_uuid = None
        group_id = None
        show_in_library = True
        if channel_id is not None:
            channel_uuid = self._parse_uuid(channel_id)
            if channel_uuid is None:
                raise ValueError("channel_id must be a valid UUID")
            group = await self.session.scalar(
                select(Group).join(Channel, Channel.group_id == Group.group_id).where(
                    Channel.channel_id == channel_uuid,
                    Channel.deleted_at.is_(None),
                    Group.deleted_at.is_(None),
                )
            )
            if group is None:
                raise LookupError("active channel not found")
            group_id = group.group_id
            show_in_library = group.group_type == GroupType.PERSONAL

        if message_id is not None:
            matching_message_id = await self.session.scalar(
                select(Message.message_id).where(
                    Message.message_id == message_id,
                    Message.channel_id == channel_uuid,
                    Message.deleted_at.is_(None),
                ).with_for_update(read=True)
            )
            if matching_message_id is None:
                raise LookupError("active message not found in the supplied channel")

        now = datetime.now(timezone.utc)
        orm_attachment = ORMAttachment(
            uploaded_by=uploader_uuid,
            channel_id=channel_uuid,
            group_id=group_id,
            message_id=message_id,
            title=title,
            file_name=file_name,
            file_type=file_type,
            file_size_bytes=file_size_bytes,
            object_path=object_path,
            processing_status=AttachmentStatus.QUEUED,
            processing_progress=0,
            show_in_library=show_in_library,
            uploaded_at=now,
            last_updated_at=now,
        )
        self.session.add(orm_attachment)
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(orm_attachment)
        return self._to_domain(orm_attachment)

    async def get_attachment_by_id(
        self,
        attachment_id: int,
    ) -> NoteAttachment | None:
        """Load one non-deleted attachment for trusted processing code."""

        attachment = await self.session.scalar(
            select(ORMAttachment).where(
                ORMAttachment.attachment_id == attachment_id,
                ORMAttachment.deleted_at.is_(None),
            )
        )
        return self._to_domain(attachment) if attachment is not None else None

    async def get_owned_attachment(
        self,
        *,
        attachment_id: int,
        user_id: str,
    ) -> NoteAttachment | None:
        """Load a note-library upload or authorized group attachment."""

        user_uuid = self._parse_uuid(user_id)
        if user_uuid is None:
            return None
        statement = (
            select(ORMAttachment)
            .outerjoin(
                Membership,
                Membership.group_id == ORMAttachment.group_id,
            )
            .where(
                ORMAttachment.attachment_id == attachment_id,
                ORMAttachment.deleted_at.is_(None),
                or_(
                    (
                        ORMAttachment.show_in_library.is_(True)
                        & (ORMAttachment.uploaded_by == user_uuid)
                    ),
                    (
                        ORMAttachment.channel_id.is_not(None)
                        & (Membership.user_id == user_uuid)
                    ),
                ),
            )
            .distinct()
        )
        attachment = await self.session.scalar(statement)
        return self._to_domain(attachment) if attachment is not None else None

    async def list_note_library_attachments(
        self,
        *,
        user_id: str,
        offset: int,
        limit: int,
        processing_status: NoteProcessingStatus | None = None,
    ) -> tuple[list[NoteAttachment], int]:
        """List only the authenticated student's active My Notes uploads."""

        user_uuid = self._parse_uuid(user_id)
        if user_uuid is None:
            return [], 0
        filters = [
            ORMAttachment.uploaded_by == user_uuid,
            ORMAttachment.show_in_library.is_(True),
            ORMAttachment.deleted_at.is_(None),
        ]
        if processing_status is not None:
            filters.append(
                ORMAttachment.processing_status
                == AttachmentStatus(processing_status.value)
            )
        total = await self.session.scalar(
            select(func.count())
            .select_from(ORMAttachment)
            .where(*filters)
        )
        result = await self.session.scalars(
            select(ORMAttachment)
            .where(*filters)
            .order_by(ORMAttachment.uploaded_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return [self._to_domain(item) for item in result.all()], total or 0

    async def update_processing_status(
        self,
        *,
        attachment_id: int,
        processing_status: NoteProcessingStatus,
        processing_progress: int,
        processing_error: str | None = None,
    ) -> NoteAttachment | None:
        """Persist a processing transition made by the RAG pipeline."""

        attachment = await self.session.scalar(
            select(ORMAttachment).where(
                ORMAttachment.attachment_id == attachment_id,
                ORMAttachment.deleted_at.is_(None),
            )
        )
        if attachment is None:
            return None
        # Validate a detached domain value before making the ORM row dirty.
        # A later query/commit therefore cannot autoflush a rejected state.
        validated = replace(
            self._to_domain(attachment),
            processing_status=processing_status,
            processing_progress=processing_progress,
            processing_error=processing_error,
            updated_at=datetime.now(timezone.utc),
        )
        attachment.processing_status = AttachmentStatus(
            validated.processing_status.value
        )
        attachment.processing_progress = validated.processing_progress
        attachment.processing_error = validated.processing_error
        attachment.last_updated_at = validated.updated_at
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(attachment)
        return self._to_domain(attachment)

    async def soft_delete_owned_attachment(
        self,
        *,
        attachment_id: int,
        user_id: str,
        deleted_at: datetime,
    ) -> bool:
        """Soft-delete metadata only after applying ownership rules."""

        owned = await self.get_owned_attachment(
            attachment_id=attachment_id,
            user_id=user_id,
        )
        if owned is None:
            return False
        attachment = await self.session.scalar(
            select(ORMAttachment).where(
                ORMAttachment.attachment_id == attachment_id,
                ORMAttachment.deleted_at.is_(None),
            )
        )
        if attachment is None:
            return False
        attachment.deleted_at = deleted_at
        attachment.last_updated_at = deleted_at
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return True
