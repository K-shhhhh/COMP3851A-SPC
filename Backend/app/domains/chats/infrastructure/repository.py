"""PostgreSQL persistence for personal AI Assistant conversations."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.chats.domain.models import (
    ChatMessage,
    ChatMessageRole,
    ChatMessageStatus,
    ChatSource,
    PersonalChat,
)
from app.domains.chats.domain.repository import ChatRepository
from app.models.orm_models import (
    AIMode,
    AIResponse,
    AIResponseSource,
    Attachment,
    Channel,
    Chunk,
    Group,
    GroupType,
    Message,
)


_ASSISTANT_ID_OFFSET = 1_000_000_000


class PostgreSQLChatRepository(ChatRepository):
    """Represent personal conversations as channels in a personal group."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _parse_uuid(value: str) -> uuid.UUID | None:
        try:
            return uuid.UUID(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_chat(
        channel: Channel,
        group: Group,
        *,
        preview: str | None = None,
    ) -> PersonalChat:
        return PersonalChat(
            chat_id=str(channel.channel_id),
            owner_id=str(group.created_by),
            title=channel.channel_name,
            created_at=channel.created_at,
            updated_at=channel.last_updated_at or channel.created_at,
            last_message_preview=preview,
            deleted_at=channel.deleted_at,
        )

    async def _latest_preview(self, channel_id: uuid.UUID) -> str | None:
        return await self.session.scalar(
            select(Message.message_content)
            .where(
                Message.channel_id == channel_id,
                Message.deleted_at.is_(None),
            )
            .order_by(Message.sent_at.desc())
            .limit(1)
        )

    async def create_chat(self, *, owner_id: str, title: str) -> PersonalChat:
        owner_uuid = self._parse_uuid(owner_id)
        if owner_uuid is None:
            raise ValueError("owner_id must be a valid UUID")

        personal_group = await self.session.scalar(
            select(Group).where(
                Group.created_by == owner_uuid,
                Group.group_type == GroupType.PERSONAL,
                Group.deleted_at.is_(None),
            )
        )
        if personal_group is None:
            raise LookupError("personal AI Assistant group not found")

        now = datetime.now(timezone.utc)
        channel = Channel(
            channel_name=title,
            group_id=personal_group.group_id,
            description="Personal AI Assistant conversation",
            created_by=owner_uuid,
            created_at=now,
            last_updated_at=now,
        )
        self.session.add(channel)
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(channel)
        return self._to_chat(channel, personal_group)

    async def list_owned_chats(
        self,
        *,
        owner_id: str,
        offset: int,
        limit: int,
    ) -> tuple[list[PersonalChat], int]:
        owner_uuid = self._parse_uuid(owner_id)
        if owner_uuid is None:
            return [], 0

        filters = [
            Group.created_by == owner_uuid,
            Group.group_type == GroupType.PERSONAL,
            Group.deleted_at.is_(None),
            Channel.deleted_at.is_(None),
        ]
        total = await self.session.scalar(
            select(func.count())
            .select_from(Channel)
            .join(Group, Group.group_id == Channel.group_id)
            .where(*filters)
        )
        result = await self.session.execute(
            select(Channel, Group)
            .join(Group, Group.group_id == Channel.group_id)
            .where(*filters)
            .order_by(
                func.coalesce(
                    Channel.last_updated_at,
                    Channel.created_at,
                ).desc()
            )
            .offset(offset)
            .limit(limit)
        )
        chats = []
        for channel, group in result.all():
            chats.append(
                self._to_chat(
                    channel,
                    group,
                    preview=await self._latest_preview(channel.channel_id),
                )
            )
        return chats, total or 0

    async def get_owned_chat(
        self,
        *,
        chat_id: str,
        owner_id: str,
    ) -> PersonalChat | None:
        chat_uuid = self._parse_uuid(chat_id)
        owner_uuid = self._parse_uuid(owner_id)
        if chat_uuid is None or owner_uuid is None:
            return None

        row = (
            await self.session.execute(
                select(Channel, Group)
                .join(Group, Group.group_id == Channel.group_id)
                .where(
                    Channel.channel_id == chat_uuid,
                    Channel.deleted_at.is_(None),
                    Group.created_by == owner_uuid,
                    Group.group_type == GroupType.PERSONAL,
                    Group.deleted_at.is_(None),
                )
            )
        ).first()
        if row is None:
            return None
        channel, group = row
        return self._to_chat(
            channel,
            group,
            preview=await self._latest_preview(channel.channel_id),
        )

    async def rename_owned_chat(
        self,
        *,
        chat_id: str,
        owner_id: str,
        title: str,
    ) -> PersonalChat | None:
        owned = await self.get_owned_chat(chat_id=chat_id, owner_id=owner_id)
        if owned is None:
            return None

        channel = await self.session.get(Channel, uuid.UUID(chat_id))
        if channel is None:
            return None
        channel.channel_name = title
        channel.last_updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        return await self.get_owned_chat(chat_id=chat_id, owner_id=owner_id)

    async def soft_delete_owned_chat(
        self,
        *,
        chat_id: str,
        owner_id: str,
        deleted_at: datetime,
    ) -> bool:
        owned = await self.get_owned_chat(chat_id=chat_id, owner_id=owner_id)
        if owned is None:
            return False
        channel = await self.session.get(Channel, uuid.UUID(chat_id))
        if channel is None:
            return False
        channel.deleted_at = deleted_at
        channel.last_updated_at = deleted_at
        await self.session.commit()
        return True

    async def create_message(
        self,
        *,
        chat_id: str,
        role: ChatMessageRole,
        content: str,
        sources: tuple[ChatSource, ...] = (),
    ) -> ChatMessage:
        chat_uuid = self._parse_uuid(chat_id)
        if chat_uuid is None:
            raise ValueError("chat_id must be a valid UUID")

        row = (
            await self.session.execute(
                select(Channel, Group)
                .join(Group, Group.group_id == Channel.group_id)
                .where(
                    Channel.channel_id == chat_uuid,
                    Channel.deleted_at.is_(None),
                    Group.group_type == GroupType.PERSONAL,
                    Group.deleted_at.is_(None),
                )
            )
        ).first()
        if row is None:
            raise ValueError("cannot add a message to a missing chat")
        channel, group = row
        now = datetime.now(timezone.utc)

        if role == ChatMessageRole.USER:
            message = Message(
                user_id=group.created_by,
                channel_id=channel.channel_id,
                message_content=content,
                ai_mode_used=AIMode.DEFAULT,
                sent_at=now,
            )
            self.session.add(message)
            channel.last_updated_at = now
            await self.session.commit()
            await self.session.refresh(message)
            return ChatMessage(
                message_id=message.message_id,
                chat_id=chat_id,
                role=role,
                content=content,
                status=ChatMessageStatus.COMPLETED,
                created_at=message.sent_at,
            )

        if role != ChatMessageRole.ASSISTANT:
            raise ValueError("only user and assistant messages are supported")

        question = await self.session.scalar(
            select(Message)
            .where(
                Message.channel_id == chat_uuid,
                Message.deleted_at.is_(None),
            )
            .order_by(Message.sent_at.desc())
            .limit(1)
        )
        if question is None:
            raise ValueError("assistant response requires a user message")

        response = AIResponse(
            message_id=question.message_id,
            ai_mode_used=AIMode.DEFAULT,
            response={"content": content},
            confidence_score=None,
            attempt_number=1,
            is_selected=True,
            execution_time_ms=0,
            token_count=0,
            generated_at=now,
        )
        self.session.add(response)
        await self.session.flush()
        for source in sources:
            self.session.add(
                AIResponseSource(
                    response_id=response.response_id,
                    chunk_id=source.chunk_id,
                    node_id=None,
                    edge_id=None,
                    similarity_score=0.0,
                    rerank_score=None,
                    is_used_in_prompt=True,
                )
            )
        channel.last_updated_at = now
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(response)
        return ChatMessage(
            message_id=_ASSISTANT_ID_OFFSET + response.response_id,
            chat_id=chat_id,
            role=role,
            content=content,
            status=ChatMessageStatus.COMPLETED,
            created_at=response.generated_at,
            sources=sources,
        )

    async def _response_sources(
        self,
        response_id: int,
    ) -> tuple[ChatSource, ...]:
        rows = await self.session.execute(
            select(Chunk, Attachment)
            .join(Attachment, Attachment.attachment_id == Chunk.attachment_id)
            .join(
                AIResponseSource,
                AIResponseSource.chunk_id == Chunk.chunk_id,
            )
            .where(AIResponseSource.response_id == response_id)
        )
        return tuple(
            ChatSource(
                note_id=attachment.attachment_id,
                note_title=attachment.title,
                chunk_id=chunk.chunk_id,
                page=chunk.source_page,
            )
            for chunk, attachment in rows.all()
        )

    async def list_messages(
        self,
        *,
        chat_id: str,
        offset: int,
        limit: int,
    ) -> tuple[list[ChatMessage], int]:
        chat_uuid = self._parse_uuid(chat_id)
        if chat_uuid is None:
            return [], 0

        message_result = await self.session.scalars(
            select(Message)
            .where(
                Message.channel_id == chat_uuid,
                Message.deleted_at.is_(None),
            )
            .order_by(Message.sent_at)
        )
        history: list[ChatMessage] = []
        for message in message_result.all():
            history.append(
                ChatMessage(
                    message_id=message.message_id,
                    chat_id=chat_id,
                    role=ChatMessageRole.USER,
                    content=message.message_content,
                    status=ChatMessageStatus.COMPLETED,
                    created_at=message.sent_at,
                )
            )
            response_result = await self.session.scalars(
                select(AIResponse)
                .where(
                    AIResponse.message_id == message.message_id,
                    AIResponse.is_selected.is_(True),
                )
                .order_by(AIResponse.attempt_number)
            )
            for response in response_result.all():
                history.append(
                    ChatMessage(
                        message_id=(
                            _ASSISTANT_ID_OFFSET + response.response_id
                        ),
                        chat_id=chat_id,
                        role=ChatMessageRole.ASSISTANT,
                        content=str(response.response.get("content", "")),
                        status=ChatMessageStatus.COMPLETED,
                        created_at=response.generated_at,
                        sources=await self._response_sources(
                            response.response_id
                        ),
                    )
                )
        return history[offset : offset + limit], len(history)
