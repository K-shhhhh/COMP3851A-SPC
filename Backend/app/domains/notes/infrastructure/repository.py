"""PostgreSQL integration point for attachment metadata.

The database developer implements every ``AttachmentRepository`` operation in
this adapter. The local Notes endpoints deliberately use
``InMemoryAttachmentRepository`` until that integration is ready.
"""

from app.domains.notes.domain.repository import AttachmentRepository


class PostgreSQLAttachmentRepository(AttachmentRepository):
    """Declare the pending PostgreSQL attachment repository adapter."""


# import uuid
# from datetime import datetime, timezone

# from sqlalchemy import func, or_, select
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.domains.notes.domain.models import (
#     NoteAttachment,
#     NoteProcessingStatus,
# )
# from app.domains.notes.domain.repository import AttachmentRepository

# from app.models.orm_models import (
#     Attachment as ORMAttachment,
#     AttachmentStatus,
#     Channel,
#     Membership,
# )


# class PostgreSQLAttachmentRepository(AttachmentRepository):

#     def __init__(self, session: AsyncSession) -> None:
#         self.session = session

# @staticmethod
# def _to_domain(attachment: ORMAttachment) -> NoteAttachment:
#     return NoteAttachment(
#         attachment_id=attachment.attachment_id,
#         uploaded_by=str(attachment.uploaded_by),
#         title=attachment.title,
#         file_name=attachment.file_name,
#         file_type=attachment.file_type,
#         file_size_bytes=attachment.file_size_bytes,
#         object_path=attachment.object_path,
#         processing_status=NoteProcessingStatus(
#             attachment.processing_status.value
#         ),
#         processing_progress=attachment.processing_progress,
#         uploaded_at=attachment.uploaded_at,
#         updated_at=attachment.last_updated_at,
#         channel_id=(
#             str(attachment.channel_id)
#             if attachment.channel_id is not None
#             else None
#         ),
#         message_id=attachment.message_id,
#         processing_error=attachment.processing_error,
#         deleted_at=attachment.deleted_at,
#     )

#     async def create_attachment(
#         self,
#         *,
#         uploaded_by: uuid.UUID,
#         title: str,
#         file_name: str,
#         file_type: str,
#         file_size_bytes: int,
#         object_path: str,
#         channel_id: uuid.UUID | None = None,
#         message_id: int | None = None,
#     ) -> NoteAttachment:

#         now = datetime.now(timezone.utc)

#         group_id: uuid.UUID | None = None

#         # Our DB stores group_id even though the domain model hides it.
#         if channel_id is not None:
#             stmt = select(Channel.group_id).where(
#                 Channel.channel_id == channel_id,
#                 Channel.deleted_at.is_(None),
#             )

#             group_id = await self.session.scalar(stmt)

#             if group_id is None:
#                 raise LookupError(f"Channel {channel_id} not found")

#         orm_attachment = ORMAttachment(
#             uploaded_by=uploaded_by,
#             channel_id=channel_id,
#             group_id=group_id,
#             message_id=message_id,
#             title=title,
#             file_name=file_name,
#             file_type=file_type,
#             file_size_bytes=file_size_bytes,
#             object_path=object_path,
#             processing_status=AttachmentStatus.QUEUED,
#             processing_progress=0,
#             uploaded_at=now,
#         )

#         self.session.add(orm_attachment)

#         try:
#             await self.session.commit()
#         except Exception:
#             await self.session.rollback()
#             raise

#         await self.session.refresh(orm_attachment)

#         return self._to_domain(orm_attachment)

#     async def get_attachment_by_id(
#         self,
#         attachment_id: int,
#     ) -> NoteAttachment | None:

#         stmt = select(ORMAttachment).where(
#             ORMAttachment.attachment_id == attachment_id,
#             ORMAttachment.deleted_at.is_(None),
#         )

#         attachment = await self.session.scalar(stmt)

#         if attachment is None:
#             return None

#         return self._to_domain(attachment)

#     async def get_owned_attachment(
#         self,
#         *,
#         attachment_id: int,
#         user_id: uuid.UUID,
#     ) -> NoteAttachment | None:

#         stmt = (
#             select(ORMAttachment)
#             .outerjoin(
#                 Membership,
#                 Membership.group_id == ORMAttachment.group_id,
#             )
#             .where(
#                 ORMAttachment.attachment_id == attachment_id,
#                 ORMAttachment.deleted_at.is_(None),

#                 or_(
#                     # Notes Library attachment
#                     (
#                         ORMAttachment.channel_id.is_(None)
#                         & (ORMAttachment.uploaded_by == user_id)
#                     ),

#                     # Channel/group attachment
#                     (
#                         ORMAttachment.channel_id.is_not(None)
#                         & (Membership.user_id == user_id)
#                     ),
#                 ),
#             )
#         )

#         attachment = await self.session.scalar(stmt)

#         if attachment is None:
#             return None

#         return self._to_domain(attachment)

#     async def list_note_library_attachments(
#         self,
#         *,
#         user_id: uuid.UUID,
#         offset: int,
#         limit: int,
#         processing_status: NoteProcessingStatus | None = None,
#     ) -> tuple[list[NoteAttachment], int]:

#         filters = [
#             ORMAttachment.uploaded_by == user_id,
#             ORMAttachment.channel_id.is_(None),
#             ORMAttachment.deleted_at.is_(None),
#         ]

#         if processing_status is not None:
#             filters.append(
#                 ORMAttachment.processing_status
#                 == AttachmentStatus(processing_status.value)
#             )

#         count_stmt = (
#             select(func.count())
#             .select_from(ORMAttachment)
#             .where(*filters)
#         )

#         total = await self.session.scalar(count_stmt)
#         total = total or 0

#         stmt = (
#             select(ORMAttachment)
#             .where(*filters)
#             .order_by(ORMAttachment.uploaded_at.desc())
#             .offset(offset)
#             .limit(limit)
#         )

#         result = await self.session.scalars(stmt)

#         return (
#             [
#                 self._to_domain(attachment)
#                 for attachment in result.all()
#             ],
#             total,
#         )

#     async def update_processing_status(
#         self,
#         *,
#         attachment_id: int,
#         processing_status: NoteProcessingStatus,
#         processing_progress: int,
#         processing_error: str | None = None,
#     ) -> NoteAttachment | None:

#         stmt = select(ORMAttachment).where(
#             ORMAttachment.attachment_id == attachment_id,
#             ORMAttachment.deleted_at.is_(None),
#         )

#         attachment = await self.session.scalar(stmt)

#         if attachment is None:
#             return None

#         attachment.processing_status = AttachmentStatus(
#             processing_status.value
#         )
#         attachment.processing_progress = processing_progress
#         attachment.processing_error = processing_error
#         attachment.last_updated_at = datetime.now(timezone.utc)

#         try:
#             await self.session.commit()
#         except Exception:
#             await self.session.rollback()
#             raise

#         await self.session.refresh(attachment)

#         return self._to_domain(attachment)

#     async def soft_delete_owned_attachment(
#         self,
#         *,
#         attachment_id: int,
#         user_id: uuid.UUID,
#         deleted_at: datetime,
#     ) -> bool:

#         # Reuse the authorization rules.
#         owned_attachment = await self.get_owned_attachment(
#             attachment_id=attachment_id,
#             user_id=user_id,
#         )

#         if owned_attachment is None:
#             return False

#         stmt = select(ORMAttachment).where(
#             ORMAttachment.attachment_id == attachment_id,
#             ORMAttachment.deleted_at.is_(None),
#         )

#         attachment = await self.session.scalar(stmt)

#         if attachment is None:
#             return False

#         attachment.deleted_at = deleted_at
#         attachment.last_updated_at = deleted_at

#         try:
#             await self.session.commit()
#         except Exception:
#             await self.session.rollback()
#             raise

#         return True