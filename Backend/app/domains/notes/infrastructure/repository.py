"""PostgreSQL persistence for uploaded note metadata."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.notes.domain.models import NoteAttachment, NoteProcessingStatus
from app.domains.notes.domain.repository import AttachmentRepository
from app.models.orm_models import (
    Attachment as ORMAttachment,
    AttachmentStatus,
    Channel,
    Membership,
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
        channel_id: str | None = None,
        message_id: int | None = None,
    ) -> NoteAttachment:
        """Create queued metadata after validation and private file storage."""

        uploader_uuid = self._parse_uuid(uploaded_by)
        if uploader_uuid is None:
            raise ValueError("uploaded_by must be a valid UUID")

        channel_uuid = None
        group_id = None
        if channel_id is not None:
            channel_uuid = self._parse_uuid(channel_id)
            if channel_uuid is None:
                raise ValueError("channel_id must be a valid UUID")
            group_id = await self.session.scalar(
                select(Channel.group_id).where(
                    Channel.channel_id == channel_uuid,
                    Channel.deleted_at.is_(None),
                )
            )
            if group_id is None:
                raise LookupError("active channel not found")

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
                        ORMAttachment.channel_id.is_(None)
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
            ORMAttachment.channel_id.is_(None),
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
        attachment.processing_status = AttachmentStatus(
            processing_status.value
        )
        attachment.processing_progress = processing_progress
        attachment.processing_error = processing_error
        attachment.last_updated_at = datetime.now(timezone.utc)
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
