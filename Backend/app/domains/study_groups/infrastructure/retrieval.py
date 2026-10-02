"""Retrieve ready grounding content for one exact Study Group channel."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.chats.domain.models import ChatSource
from app.domains.chats.domain.retrieval import GroundingChunk
from app.domains.study_groups.domain.retrieval import StudyGroupReadyChunkRepository
from app.models.orm_models import (
    Attachment, AttachmentStatus, Channel, Chunk, Group, GroupType,
)


class PostgreSQLStudyGroupReadyChunkRepository(StudyGroupReadyChunkRepository):
    """Enforce group/channel boundaries before content reaches the AI adapter."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_ready_chunks_for_channel(
        self, *, group_id: str, channel_id: str,
    ) -> tuple[GroundingChunk, ...]:
        try:
            group_uuid, channel_uuid = UUID(group_id), UUID(channel_id)
        except (ValueError, TypeError, AttributeError):
            return ()

        rows = await self.session.execute(
            select(Chunk, Attachment)
            .join(Attachment, Attachment.attachment_id == Chunk.attachment_id)
            .join(Channel, Channel.channel_id == Attachment.channel_id)
            .join(Group, Group.group_id == Channel.group_id)
            .where(
                Group.group_id == group_uuid,
                Group.group_type.in_((GroupType.PUBLIC, GroupType.PRIVATE)),
                Group.deleted_at.is_(None),
                Channel.channel_id == channel_uuid,
                Channel.deleted_at.is_(None),
                Attachment.group_id == group_uuid,
                Attachment.processing_status == AttachmentStatus.READY,
                Attachment.deleted_at.is_(None),
                Chunk.deleted_at.is_(None),
            )
            .order_by(Attachment.attachment_id, Chunk.chunk_order, Chunk.chunk_id)
        )
        return tuple(
            GroundingChunk(
                content=chunk.chunk_content,
                source=ChatSource(
                    note_id=attachment.attachment_id,
                    note_title=attachment.title,
                    chunk_id=chunk.chunk_id,
                    page=chunk.source_page,
                ),
            )
            for chunk, attachment in rows.all()
        )

    async def search_ready_chunks_for_channel(
        self,
        *,
        group_id: str,
        channel_id: str,
        query_embedding: tuple[float, ...],
        limit: int,
    ) -> tuple[GroundingChunk, ...]:
        """Declare the channel-scoped pgvector search implemented by the DB owner."""

        raise NotImplementedError(
            "PostgreSQL Study Group HNSW retrieval is not implemented."
        )
