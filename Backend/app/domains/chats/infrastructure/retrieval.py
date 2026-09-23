"""PostgreSQL chunk persistence and permission-scoped retrieval."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.chats.domain.models import ChatSource
from app.domains.chats.domain.retrieval import (
    GroundingChunk,
    ReadyNoteChunkRepository,
)
from app.models.orm_models import (
    Attachment,
    AttachmentStatus,
    Chunk,
)


class PostgreSQLReadyNoteChunkRepository(ReadyNoteChunkRepository):
    """Persist embedded chunks and retrieve only authorized ready content."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def replace_embedded_attachment_chunks(
        self,
        *,
        attachment_id: int,
        chunks: list[dict],
    ) -> None:
        """Upsert one attachment's derived chunks by stable chunk order."""

        existing_result = await self.session.scalars(
            select(Chunk).where(Chunk.attachment_id == attachment_id)
        )
        existing = {item.chunk_order: item for item in existing_result.all()}
        now = datetime.now(timezone.utc)
        active_orders: set[int] = set()

        for payload in chunks:
            order = int(payload["chunk_id"])
            embedding = list(payload["embedding"])
            if len(embedding) != 768:
                raise ValueError("chunk embedding must contain 768 values")

            active_orders.add(order)
            chunk = existing.get(order)
            if chunk is None:
                chunk = Chunk(
                    attachment_id=attachment_id,
                    chunk_order=order,
                    source_page=payload.get("source_page"),
                    source_type=payload.get("source_type", "text"),
                    chunk_content=payload["text"],
                    embedding_model_version=payload.get(
                        "embedding_model_version",
                        "nomic-embed-text",
                    ),
                    vector_embedding=embedding,
                    created_at=now,
                )
                self.session.add(chunk)
            else:
                chunk.source_page = payload.get("source_page")
                chunk.source_type = payload.get("source_type", "text")
                chunk.chunk_content = payload["text"]
                chunk.embedding_model_version = payload.get(
                    "embedding_model_version",
                    "nomic-embed-text",
                )
                chunk.vector_embedding = embedding
                chunk.deleted_at = None

        for order, old_chunk in existing.items():
            if order not in active_orders:
                old_chunk.deleted_at = now

        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    async def list_ready_chunks_for_user(
        self,
        *,
        user_id: str,
    ) -> tuple[GroundingChunk, ...]:
        """Return ready My Notes chunks owned by one authenticated student."""

        try:
            user_uuid = uuid.UUID(user_id)
        except (TypeError, ValueError):
            return ()

        result = await self.session.execute(
            select(Chunk, Attachment)
            .join(
                Attachment,
                Attachment.attachment_id == Chunk.attachment_id,
            )
            .where(
                Attachment.uploaded_by == user_uuid,
                Attachment.channel_id.is_(None),
                Attachment.processing_status == AttachmentStatus.READY,
                Attachment.deleted_at.is_(None),
                Chunk.deleted_at.is_(None),
            )
            .order_by(Chunk.attachment_id, Chunk.chunk_order)
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
            for chunk, attachment in result.all()
        )
