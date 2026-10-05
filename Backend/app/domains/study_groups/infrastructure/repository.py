"""PostgreSQL persistence for collaborative Study Group use cases.

The adapter maps SQLAlchemy rows into framework-independent domain objects.
It also repeats concurrency-sensitive membership and capacity rules inside the
database transaction so simultaneous requests cannot bypass them.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.study_groups.domain.exceptions import (
    InvalidStudyGroupError,
    StudyGroupAlreadyMemberError,
    StudyGroupFullError,
    StudyGroupChannelNameConflictError,
    StudyGroupChannelNotFoundError,
    StudyGroupMessageNotFoundError,
    InvalidStudyGroupMessageError,
)
from app.domains.study_groups.domain.models import (
    MyGroupsFilter,
    StudyGroup,
    StudyGroupMemberRole,
    StudyGroupMember,
    StudyGroupChannel,
    StudyGroupMessage,
    StudyGroupAiMode,
    StudyGroupAiResponse,
    StudyGroupMembership,
    StudyGroupSummary,
    StudyGroupVisibility,
)
from app.domains.study_groups.domain.repository import StudyGroupRepository
from app.domains.chats.domain.models import ChatSource
from app.models.orm_models import (
    ActivityStatus,
    AIMode,
    AIResponse,
    AIResponseSource,
    Attachment,
    AttachmentStatus,
    Chunk,
    Channel as ORMChannel,
    Group as ORMGroup,
    GroupType,
    MemberRole,
    Membership as ORMMembership,
    Message as ORMMessage,
    MessageMention,
    User as ORMUser,
)


class PostgreSQLStudyGroupRepository(StudyGroupRepository):
    """Store study groups and memberships in PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        """Use the request-scoped SQLAlchemy session."""

        self._session = session

    async def find_active_user_id_by_email(self, *, email: str) -> str | None:
        """Return only the ID of a matching active, non-deleted account."""

        user_id = await self._session.scalar(
            select(ORMUser.user_id).where(
                func.lower(ORMUser.email) == email.strip().lower(),
                ORMUser.status == ActivityStatus.ACTIVE,
                ORMUser.deleted_at.is_(None),
            ).order_by(ORMUser.user_id).limit(1)
        )
        return str(user_id) if user_id is not None else None

    async def list_members(
        self, *, group_id: str, offset: int, limit: int,
    ) -> tuple[list[StudyGroupMember], int]:
        """Read only public member fields from an active study group."""

        self._validate_pagination(offset, limit)
        statement = (
            select(
                ORMMembership.membership_id, ORMMembership.group_id,
                ORMMembership.user_id, ORMUser.fullname, ORMUser.email,
                ORMMembership.member_role, ORMMembership.joined_at,
            )
            .join(ORMUser, ORMUser.user_id == ORMMembership.user_id)
            .join(ORMGroup, ORMGroup.group_id == ORMMembership.group_id)
            .where(
                ORMGroup.group_id == self._uuid(group_id, "group_id"),
                ORMGroup.deleted_at.is_(None),
                ORMGroup.group_type.in_((GroupType.PUBLIC, GroupType.PRIVATE)),
                ORMUser.deleted_at.is_(None),
                ORMUser.status == ActivityStatus.ACTIVE,
            )
        )
        total = int(await self._session.scalar(
            select(func.count()).select_from(statement.subquery())
        ) or 0)
        rows = await self._session.execute(
            statement.order_by(
                (ORMMembership.member_role == MemberRole.ADMIN).desc(),
                ORMMembership.joined_at, ORMMembership.membership_id,
            ).offset(offset).limit(limit)
        )
        return [
            StudyGroupMember(
                membership_id=row.membership_id, group_id=str(row.group_id),
                user_id=str(row.user_id), full_name=row.fullname, email=row.email,
                role=StudyGroupMemberRole(row.member_role.value), joined_at=row.joined_at,
            ) for row in rows
        ], total

    @staticmethod
    def _validate_pagination(offset: int, limit: int) -> None:
        if offset < 0 or limit <= 0:
            raise ValueError("offset must be non-negative and limit must be positive")

    @staticmethod
    def _channel_query(group_id: UUID):
        """Shared active-group boundary for every channel operation."""

        return (
            select(ORMChannel)
            .join(ORMGroup, ORMGroup.group_id == ORMChannel.group_id)
            .where(
                ORMGroup.group_id == group_id,
                ORMGroup.group_type.in_((GroupType.PUBLIC, GroupType.PRIVATE)),
                ORMGroup.deleted_at.is_(None),
                ORMChannel.deleted_at.is_(None),
            )
        )

    async def _channel_row(self, group_id: UUID, channel_id: UUID, *, for_update=False):
        statement = self._channel_query(group_id).where(ORMChannel.channel_id == channel_id)
        if for_update:
            statement = statement.with_for_update(of=ORMChannel).execution_options(populate_existing=True)
        return await self._session.scalar(statement)

    @staticmethod
    def _channel_to_domain(channel: ORMChannel) -> StudyGroupChannel:
        return StudyGroupChannel(
            channel_id=str(channel.channel_id), group_id=str(channel.group_id),
            name=channel.channel_name, description=channel.description,
            created_by=str(channel.created_by), created_at=channel.created_at,
            updated_at=channel.last_updated_at or channel.created_at,
            deleted_at=channel.deleted_at,
        )

    async def list_channels(self, *, group_id: str, offset: int, limit: int):
        self._validate_pagination(offset, limit)
        statement = self._channel_query(self._uuid(group_id, "group_id"))
        total = int(await self._session.scalar(
            select(func.count()).select_from(statement.subquery())
        ) or 0)
        rows = await self._session.scalars(
            statement.order_by(ORMChannel.created_at, ORMChannel.channel_id)
            .offset(offset).limit(limit)
        )
        return [self._channel_to_domain(row) for row in rows], total

    async def get_channel(self, *, group_id: str, channel_id: str):
        row = await self._channel_row(
            self._uuid(group_id, "group_id"), self._uuid(channel_id, "channel_id"),
        )
        return self._channel_to_domain(row) if row is not None else None

    async def channel_name_exists(
        self, *, group_id: str, normalized_name: str, exclude_channel_id: str | None = None,
    ) -> bool:
        statement = self._channel_query(self._uuid(group_id, "group_id")).where(
            func.lower(ORMChannel.channel_name) == func.lower(normalized_name),
        )
        if exclude_channel_id is not None:
            statement = statement.where(
                ORMChannel.channel_id != self._uuid(exclude_channel_id, "channel_id"),
            )
        return bool(await self._session.scalar(select(statement.exists())))

    @staticmethod
    def _is_constraint(error: IntegrityError, name: str) -> bool:
        return getattr(getattr(error.orig, "diag", None), "constraint_name", None) == name

    async def create_channel(
        self, *, group_id: str, name: str, description: str | None,
        created_by: str, created_at: datetime,
    ) -> StudyGroupChannel:
        try:
            group = await self._active_group(self._uuid(group_id, "group_id"), for_update=True)
            if group is None:
                raise StudyGroupChannelNotFoundError("Study group not found.")
            if await self.channel_name_exists(group_id=group_id, normalized_name=name):
                raise StudyGroupChannelNameConflictError("An active channel with that name already exists.")
            channel = ORMChannel(
                group_id=group.group_id, channel_name=name, description=description,
                created_by=self._uuid(created_by, "created_by"),
                created_at=created_at, last_updated_at=created_at,
            )
            self._session.add(channel)
            await self._session.flush()
            result = self._channel_to_domain(channel)
            await self._session.commit()
            return result
        except IntegrityError as error:
            await self._session.rollback()
            if self._is_constraint(error, "uq_channels_group_name"):
                raise StudyGroupChannelNameConflictError("An active channel with that name already exists.") from error
            raise
        except Exception:
            await self._session.rollback()
            raise

    async def update_channel(
        self, *, group_id: str, channel_id: str, name: str,
        description: str | None, updated_at: datetime,
    ) -> StudyGroupChannel:
        try:
            group_uuid = self._uuid(group_id, "group_id")
            if await self._active_group(group_uuid, for_update=True) is None:
                raise StudyGroupChannelNotFoundError("Study group not found.")
            channel = await self._channel_row(group_uuid, self._uuid(channel_id, "channel_id"), for_update=True)
            if channel is None:
                raise StudyGroupChannelNotFoundError("Study group channel not found.")
            if await self.channel_name_exists(
                group_id=group_id, normalized_name=name, exclude_channel_id=channel_id,
            ):
                raise StudyGroupChannelNameConflictError("An active channel with that name already exists.")
            channel.channel_name = name
            channel.description = description
            channel.last_updated_at = updated_at
            result = self._channel_to_domain(channel)
            await self._session.commit()
            return result
        except IntegrityError as error:
            await self._session.rollback()
            if self._is_constraint(error, "uq_channels_group_name"):
                raise StudyGroupChannelNameConflictError("An active channel with that name already exists.") from error
            raise
        except Exception:
            await self._session.rollback()
            raise

    async def soft_delete_channel(
        self, *, group_id: str, channel_id: str, deleted_at: datetime,
    ) -> bool:
        try:
            group_uuid = self._uuid(group_id, "group_id")
            if await self._active_group(group_uuid, for_update=True) is None:
                await self._session.rollback()
                return False
            channel = await self._channel_row(group_uuid, self._uuid(channel_id, "channel_id"), for_update=True)
            if channel is None:
                await self._session.rollback()
                return False
            channel.deleted_at = deleted_at
            channel.last_updated_at = deleted_at
            await self._session.commit()
            return True
        except Exception:
            await self._session.rollback()
            raise

    @staticmethod
    def _message_query(group_id: UUID, channel_id: UUID):
        return (
            select(ORMMessage)
            .join(ORMChannel, ORMChannel.channel_id == ORMMessage.channel_id)
            .join(ORMGroup, ORMGroup.group_id == ORMChannel.group_id)
            .where(
                ORMGroup.group_id == group_id,
                ORMGroup.group_type.in_((GroupType.PUBLIC, GroupType.PRIVATE)),
                ORMGroup.deleted_at.is_(None),
                ORMChannel.channel_id == channel_id,
                ORMChannel.deleted_at.is_(None),
                ORMMessage.deleted_at.is_(None),
            )
        )

    async def _message_row(self, group_id: UUID, channel_id: UUID, message_id: int, *, for_update=False):
        statement = self._message_query(group_id, channel_id).where(ORMMessage.message_id == message_id)
        if for_update:
            statement = statement.with_for_update(of=ORMMessage).execution_options(populate_existing=True)
        return await self._session.scalar(statement)

    async def _lock_channel(self, group_id: UUID, channel_id: UUID):
        # All writes lock ancestors first, including deletes, to avoid writing
        # into a group/channel that is concurrently being soft-deleted.
        if await self._active_group(group_id, for_update=True) is None:
            return None
        return await self._channel_row(group_id, channel_id, for_update=True)

    async def _message_to_domain(self, message: ORMMessage, group_id: UUID) -> StudyGroupMessage:
        mentioned_ids = await self._session.scalars(
            select(MessageMention.user_id)
            .where(MessageMention.message_id == message.message_id)
            .order_by(MessageMention.user_id)
        )
        return StudyGroupMessage(
            message_id=message.message_id, group_id=str(group_id),
            channel_id=str(message.channel_id), author_id=str(message.user_id),
            content=message.message_content, sent_at=message.sent_at,
            mentioned_user_ids=tuple(str(user_id) for user_id in mentioned_ids),
            ai_mode_used=StudyGroupAiMode(message.ai_mode_used.value) if message.ai_mode_used is not None else None,
            ai_response=await self._selected_response(message, group_id),
            edited_at=message.edited_at, deleted_at=message.deleted_at,
        )

    @staticmethod
    def _source_query(group_id: UUID, channel_id: UUID):
        """Citations must resolve to ready content in this exact channel."""

        return (
            select(Chunk, Attachment)
            .join(Attachment, Attachment.attachment_id == Chunk.attachment_id)
            .join(ORMChannel, ORMChannel.channel_id == Attachment.channel_id)
            .join(ORMGroup, ORMGroup.group_id == ORMChannel.group_id)
            .where(
                ORMGroup.group_id == group_id,
                ORMGroup.group_type.in_((GroupType.PUBLIC, GroupType.PRIVATE)),
                ORMGroup.deleted_at.is_(None),
                ORMChannel.channel_id == channel_id,
                ORMChannel.deleted_at.is_(None),
                Attachment.group_id == group_id,
                Attachment.processing_status == AttachmentStatus.READY,
                Attachment.deleted_at.is_(None),
                Chunk.deleted_at.is_(None),
            )
        )

    async def _selected_response(self, message: ORMMessage, group_id: UUID) -> StudyGroupAiResponse | None:
        response = await self._session.scalar(
            select(AIResponse).where(
                AIResponse.message_id == message.message_id,
                AIResponse.is_selected.is_(True),
            ).order_by(AIResponse.attempt_number.desc(), AIResponse.response_id.desc()).limit(1)
        )
        if response is None:
            return None
        rows = await self._session.execute(
            self._source_query(group_id, message.channel_id)
            .join(AIResponseSource, AIResponseSource.chunk_id == Chunk.chunk_id)
            .where(AIResponseSource.response_id == response.response_id)
            .order_by(AIResponseSource.retrieval_id)
        )
        return StudyGroupAiResponse(
            response_id=response.response_id, mode=StudyGroupAiMode(response.ai_mode_used.value),
            content=response.response["content"], generated_at=response.generated_at,
            sources=tuple(ChatSource(
                note_id=attachment.attachment_id, note_title=attachment.title,
                chunk_id=chunk.chunk_id, page=chunk.source_page,
            ) for chunk, attachment in rows),
        )

    async def save_ai_response(
        self, *, group_id: str, channel_id: str, message_id: int,
        mode: StudyGroupAiMode, content: str, sources: tuple[ChatSource, ...],
        generated_at: datetime,
    ) -> StudyGroupMessage:
        """Save an answer, its selected status and citations atomically."""

        try:
            group_uuid = self._uuid(group_id, "group_id")
            channel_uuid = self._uuid(channel_id, "channel_id")
            if await self._lock_channel(group_uuid, channel_uuid) is None:
                raise StudyGroupMessageNotFoundError("Study group message not found.")
            message = await self._message_row(group_uuid, channel_uuid, message_id, for_update=True)
            if message is None:
                raise StudyGroupMessageNotFoundError("Study group message not found.")
            if message.ai_mode_used != AIMode(mode.value):
                raise InvalidStudyGroupMessageError("The AI mode must match the original message.")

            unique_sources = {source.chunk_id: source for source in sources}
            rows = await self._session.execute(
                self._source_query(group_uuid, channel_uuid)
                .where(Chunk.chunk_id.in_(unique_sources))
                .with_for_update(of=[Chunk, Attachment])
            )
            authorized = {chunk.chunk_id: attachment.attachment_id for chunk, attachment in rows}
            if any(authorized.get(source.chunk_id) != source.note_id for source in sources):
                raise InvalidStudyGroupMessageError("An AI citation is outside the active group channel.")

            attempt = int(await self._session.scalar(
                select(func.max(AIResponse.attempt_number)).where(AIResponse.message_id == message_id)
            ) or 0) + 1
            await self._session.execute(
                update(AIResponse).where(AIResponse.message_id == message_id)
                .values(is_selected=False)
            )
            response = AIResponse(
                message_id=message_id, ai_mode_used=AIMode(mode.value),
                response={"content": content}, generated_at=generated_at,
                attempt_number=attempt, is_selected=True,
                confidence_score=None, execution_time_ms=0, token_count=0,
            )
            self._session.add(response)
            await self._session.flush()
            self._session.add_all([
                AIResponseSource(
                    response_id=response.response_id, chunk_id=source.chunk_id,
                    similarity_score=0.0, rerank_score=None, is_used_in_prompt=True,
                ) for source in unique_sources.values()
            ])
            await self._session.flush()
            result = await self._message_to_domain(message, group_uuid)
            await self._session.commit()
            return result
        except Exception:
            await self._session.rollback()
            raise

    async def _replace_mentions(self, message_id: int, user_ids: tuple[str, ...]) -> None:
        """Replace associations inside the caller's message transaction.

        The schema names the mentioned-user FK ``user_id``; public contracts
        continue to use ``mentioned_user_ids``. The composite PK deduplicates
        pairs and both FKs cascade on physical parent deletion.
        """

        unique_ids = {self._uuid(user_id, "mentioned_user_id") for user_id in user_ids}
        await self._session.execute(
            delete(MessageMention).where(MessageMention.message_id == message_id)
        )
        self._session.add_all([
            MessageMention(message_id=message_id, user_id=user_id)
            for user_id in sorted(unique_ids)
        ])
        # Flush before mapping: sessions intentionally have autoflush=False.
        await self._session.flush()

    async def list_messages(
        self, *, group_id: str, channel_id: str, offset: int, limit: int,
    ) -> tuple[list[StudyGroupMessage], int]:
        self._validate_pagination(offset, limit)
        group_uuid = self._uuid(group_id, "group_id")
        statement = self._message_query(group_uuid, self._uuid(channel_id, "channel_id"))
        total = int(await self._session.scalar(
            select(func.count()).select_from(statement.subquery())
        ) or 0)
        messages = await self._session.scalars(
            statement.order_by(ORMMessage.sent_at, ORMMessage.message_id)
            .offset(offset).limit(limit)
        )
        return [await self._message_to_domain(message, group_uuid) for message in messages], total

    async def get_message(self, *, group_id: str, channel_id: str, message_id: int):
        group_uuid = self._uuid(group_id, "group_id")
        message = await self._message_row(group_uuid, self._uuid(channel_id, "channel_id"), message_id)
        return await self._message_to_domain(message, group_uuid) if message is not None else None

    async def create_message(
        self, *, group_id: str, channel_id: str, author_id: str, content: str,
        mentioned_user_ids: tuple[str, ...], ai_mode: StudyGroupAiMode | None, sent_at: datetime,
    ) -> StudyGroupMessage:
        try:
            group_uuid = self._uuid(group_id, "group_id")
            channel_uuid = self._uuid(channel_id, "channel_id")
            if await self._lock_channel(group_uuid, channel_uuid) is None:
                raise StudyGroupChannelNotFoundError("Study group channel not found.")
            message = ORMMessage(
                channel_id=channel_uuid, user_id=self._uuid(author_id, "author_id"),
                message_content=content, sent_at=sent_at,
                ai_mode_used=AIMode(ai_mode.value) if ai_mode is not None else None,
            )
            self._session.add(message)
            await self._session.flush()
            await self._replace_mentions(message.message_id, mentioned_user_ids)
            result = await self._message_to_domain(message, group_uuid)
            await self._session.commit()
            return result
        except Exception:
            await self._session.rollback()
            raise

    async def update_message(
        self, *, group_id: str, channel_id: str, message_id: int, content: str,
        mentioned_user_ids: tuple[str, ...], edited_at: datetime,
    ) -> StudyGroupMessage:
        try:
            group_uuid = self._uuid(group_id, "group_id")
            channel_uuid = self._uuid(channel_id, "channel_id")
            if await self._lock_channel(group_uuid, channel_uuid) is None:
                raise StudyGroupMessageNotFoundError("Study group message not found.")
            message = await self._message_row(group_uuid, channel_uuid, message_id, for_update=True)
            if message is None:
                raise StudyGroupMessageNotFoundError("Study group message not found.")
            message.message_content = content
            message.edited_at = edited_at
            await self._replace_mentions(message.message_id, mentioned_user_ids)
            result = await self._message_to_domain(message, group_uuid)
            await self._session.commit()
            return result
        except Exception:
            await self._session.rollback()
            raise

    async def soft_delete_message(
        self, *, group_id: str, channel_id: str, message_id: int, deleted_at: datetime,
    ) -> bool:
        try:
            group_uuid = self._uuid(group_id, "group_id")
            channel_uuid = self._uuid(channel_id, "channel_id")
            if await self._lock_channel(group_uuid, channel_uuid) is None:
                await self._session.rollback()
                return False
            message = await self._message_row(group_uuid, channel_uuid, message_id, for_update=True)
            if message is None:
                await self._session.rollback()
                return False
            message.deleted_at = deleted_at
            await self._session.commit()
            return True
        except Exception:
            await self._session.rollback()
            raise

    async def list_discoverable_public_groups(
        self,
        *,
        user_id: str,
        offset: int,
        limit: int,
        search: str | None = None,
    ) -> tuple[list[StudyGroupSummary], int]:
        """Return active public groups for the discovery screen."""

        user_uuid = self._uuid(user_id, "user_id")
        filters = [
            ORMGroup.deleted_at.is_(None),
            ORMGroup.group_type == GroupType.PUBLIC,
        ]

        if search:
            pattern = f"%{self._escape_like(search)}%"
            filters.append(
                or_(
                    ORMGroup.group_name.ilike(pattern, escape="\\"),
                    ORMGroup.description.ilike(pattern, escape="\\"),
                )
            )

        total = int(
            await self._session.scalar(
                select(func.count(ORMGroup.group_id)).where(*filters)
            )
            or 0
        )
        statement = (
            select(ORMGroup)
            .where(*filters)
            .order_by(
                func.coalesce(
                    ORMGroup.last_updated_at,
                    ORMGroup.created_at,
                ).desc(),
                ORMGroup.group_id,
            )
            .offset(offset)
            .limit(limit)
        )
        groups = list((await self._session.scalars(statement)).all())

        return (
            [
                await self._to_summary(group=group, user_id=user_uuid)
                for group in groups
            ],
            total,
        )

    async def list_user_groups(
        self,
        *,
        user_id: str,
        group_filter: MyGroupsFilter,
        offset: int,
        limit: int,
    ) -> tuple[list[StudyGroupSummary], int]:
        """Return active non-personal groups owned or joined by a user."""

        user_uuid = self._uuid(user_id, "user_id")
        membership_exists = select(ORMMembership.membership_id).where(
            ORMMembership.group_id == ORMGroup.group_id,
            ORMMembership.user_id == user_uuid,
        ).exists()
        filters = [
            ORMGroup.deleted_at.is_(None),
            ORMGroup.group_type.in_(
                (GroupType.PUBLIC, GroupType.PRIVATE)
            ),
            or_(ORMGroup.created_by == user_uuid, membership_exists),
        ]

        if group_filter == MyGroupsFilter.PUBLIC:
            filters.append(ORMGroup.group_type == GroupType.PUBLIC)
        elif group_filter == MyGroupsFilter.PRIVATE:
            filters.append(ORMGroup.group_type == GroupType.PRIVATE)
        elif group_filter == MyGroupsFilter.OWNED:
            filters.append(ORMGroup.created_by == user_uuid)

        total = int(
            await self._session.scalar(
                select(func.count(ORMGroup.group_id)).where(*filters)
            )
            or 0
        )
        statement = (
            select(ORMGroup)
            .where(*filters)
            .order_by(
                func.coalesce(
                    ORMGroup.last_updated_at,
                    ORMGroup.created_at,
                ).desc(),
                ORMGroup.group_id,
            )
            .offset(offset)
            .limit(limit)
        )
        groups = list((await self._session.scalars(statement)).all())

        return (
            [
                await self._to_summary(group=group, user_id=user_uuid)
                for group in groups
            ],
            total,
        )

    async def get_group_for_user(
        self,
        *,
        group_id: str,
        user_id: str,
    ) -> StudyGroupSummary | None:
        """Return a public group or a private group visible to the user."""

        group_uuid = self._uuid(group_id, "group_id")
        user_uuid = self._uuid(user_id, "user_id")
        group = await self._active_group(group_uuid)
        if group is None:
            return None

        membership = await self._membership_row(
            group_id=group_uuid,
            user_id=user_uuid,
        )
        is_owner = group.created_by == user_uuid
        if (
            group.group_type == GroupType.PRIVATE
            and membership is None
            and not is_owner
        ):
            return None

        return await self._to_summary(
            group=group,
            user_id=user_uuid,
            membership=membership,
        )

    async def get_group(self, *, group_id: str) -> StudyGroup | None:
        """Return one active public/private group without user projection."""

        group = await self._active_group(
            self._uuid(group_id, "group_id")
        )
        return self._to_domain(group) if group is not None else None

    async def create_group(
        self,
        *,
        name: str,
        description: str | None,
        visibility: StudyGroupVisibility,
        created_by: str,
        max_members: int,
    ) -> StudyGroupSummary:
        """Create the group and creator's admin membership atomically."""

        creator_uuid = self._uuid(created_by, "created_by")
        now = datetime.now(timezone.utc)
        group = ORMGroup(
            group_name=name,
            group_type=GroupType(visibility.value),
            description=description,
            created_by=creator_uuid,
            current_admin=creator_uuid,
            max_members=max_members,
            created_at=now,
            last_updated_at=now,
        )

        try:
            self._session.add(group)
            await self._session.flush()
            membership = ORMMembership(
                user_id=creator_uuid,
                group_id=group.group_id,
                member_role=MemberRole.ADMIN,
                joined_at=now,
            )
            self._session.add(membership)
            await self._session.commit()
            await self._session.refresh(group)
            await self._session.refresh(membership)
        except Exception:
            await self._session.rollback()
            raise

        return await self._to_summary(
            group=group,
            user_id=creator_uuid,
            membership=membership,
        )

    async def update_group(
        self,
        *,
        group_id: str,
        name: str,
        description: str | None,
        visibility: StudyGroupVisibility,
        max_members: int,
        updated_at: datetime,
    ) -> StudyGroup:
        """Update an active group after application authorization."""

        group = await self._active_group(
            self._uuid(group_id, "group_id"),
            for_update=True,
        )
        if group is None:
            raise LookupError("Study group not found.")

        if max_members < await self._count_members_uuid(group.group_id):
            raise InvalidStudyGroupError(
                "Maximum members cannot be lower than the current member count."
            )

        group.group_name = name
        group.description = description
        group.group_type = GroupType(visibility.value)
        group.max_members = max_members
        group.last_updated_at = updated_at
        try:
            await self._session.commit()
            await self._session.refresh(group)
        except Exception:
            await self._session.rollback()
            raise
        return self._to_domain(group)

    async def soft_delete_group(
        self,
        *,
        group_id: str,
        deleted_at: datetime,
    ) -> bool:
        """Soft-delete a group while retaining related history."""

        group = await self._active_group(
            self._uuid(group_id, "group_id"),
            for_update=True,
        )
        if group is None:
            return False

        group.deleted_at = deleted_at
        group.last_updated_at = deleted_at
        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        return True

    async def get_membership(
        self,
        *,
        group_id: str,
        user_id: str,
    ) -> StudyGroupMembership | None:
        """Return a membership only while its group remains active."""

        group_uuid = self._uuid(group_id, "group_id")
        if await self._active_group(group_uuid) is None:
            return None
        membership = await self._membership_row(
            group_id=group_uuid,
            user_id=self._uuid(user_id, "user_id"),
        )
        return (
            self._membership_to_domain(membership)
            if membership is not None
            else None
        )

    async def create_membership(
        self,
        *,
        group_id: str,
        user_id: str,
        role: StudyGroupMemberRole,
        joined_at: datetime,
    ) -> StudyGroupMembership:
        """Create a unique membership while locking capacity checks."""

        group_uuid = self._uuid(group_id, "group_id")
        user_uuid = self._uuid(user_id, "user_id")
        group = await self._active_group(group_uuid, for_update=True)
        if group is None:
            raise LookupError("Study group not found.")

        if await self._membership_row(
            group_id=group_uuid,
            user_id=user_uuid,
        ) is not None:
            raise StudyGroupAlreadyMemberError(
                "You are already a member of this study group."
            )
        if await self._count_members_uuid(group_uuid) >= group.max_members:
            raise StudyGroupFullError(
                "This study group has reached its member limit."
            )

        membership = ORMMembership(
            group_id=group_uuid,
            user_id=user_uuid,
            member_role=MemberRole(role.value),
            joined_at=joined_at,
        )
        self._session.add(membership)
        try:
            await self._session.commit()
            await self._session.refresh(membership)
        except IntegrityError as exc:
            await self._session.rollback()
            raise StudyGroupAlreadyMemberError(
                "You are already a member of this study group."
            ) from exc
        except Exception:
            await self._session.rollback()
            raise
        return self._membership_to_domain(membership)

    async def delete_membership(
        self,
        *,
        group_id: str,
        user_id: str,
    ) -> bool:
        """Hard-delete an active membership when a user leaves."""

        membership = await self._membership_row(
            group_id=self._uuid(group_id, "group_id"),
            user_id=self._uuid(user_id, "user_id"),
        )
        if membership is None:
            return False
        try:
            await self._session.delete(membership)
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        return True

    async def count_members(self, *, group_id: str) -> int:
        """Count memberships associated with one active group."""

        group_uuid = self._uuid(group_id, "group_id")
        if await self._active_group(group_uuid) is None:
            return 0
        return await self._count_members_uuid(group_uuid)

    async def _active_group(
        self,
        group_id: UUID,
        *,
        for_update: bool = False,
    ) -> ORMGroup | None:
        """Return one active non-personal ORM group."""

        statement = select(ORMGroup).where(
            ORMGroup.group_id == group_id,
            ORMGroup.deleted_at.is_(None),
            ORMGroup.group_type.in_(
                (GroupType.PUBLIC, GroupType.PRIVATE)
            ),
        )
        if for_update:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        return await self._session.scalar(statement)

    async def _membership_row(
        self,
        *,
        group_id: UUID,
        user_id: UUID,
    ) -> ORMMembership | None:
        """Return the unique membership row for a user/group pair."""

        return await self._session.scalar(
            select(ORMMembership).where(
                ORMMembership.group_id == group_id,
                ORMMembership.user_id == user_id,
            )
        )

    async def _count_members_uuid(self, group_id: UUID) -> int:
        """Count membership rows using an already validated UUID."""

        return int(
            await self._session.scalar(
                select(func.count(ORMMembership.membership_id)).where(
                    ORMMembership.group_id == group_id
                )
            )
            or 0
        )

    async def _to_summary(
        self,
        *,
        group: ORMGroup,
        user_id: UUID,
        membership: ORMMembership | None = None,
    ) -> StudyGroupSummary:
        """Build the current user's safe group projection."""

        if membership is None:
            membership = await self._membership_row(
                group_id=group.group_id,
                user_id=user_id,
            )
        return StudyGroupSummary(
            group=self._to_domain(group),
            member_count=await self._count_members_uuid(group.group_id),
            is_member=membership is not None,
            is_owner=group.created_by == user_id,
            membership_role=(
                StudyGroupMemberRole(membership.member_role.value)
                if membership is not None
                else None
            ),
        )

    @staticmethod
    def _to_domain(group: ORMGroup) -> StudyGroup:
        """Map a SQLAlchemy group row into the domain model."""

        if group.group_type == GroupType.PERSONAL:
            raise ValueError("Personal groups are not Study Group records.")
        return StudyGroup(
            group_id=str(group.group_id),
            name=group.group_name,
            visibility=StudyGroupVisibility(group.group_type.value),
            description=group.description,
            created_by=str(group.created_by),
            current_admin_id=str(group.current_admin),
            max_members=group.max_members,
            created_at=group.created_at,
            updated_at=group.last_updated_at or group.created_at,
            deleted_at=group.deleted_at,
        )

    @staticmethod
    def _membership_to_domain(
        membership: ORMMembership,
    ) -> StudyGroupMembership:
        """Map a SQLAlchemy membership row into the domain model."""

        return StudyGroupMembership(
            membership_id=membership.membership_id,
            group_id=str(membership.group_id),
            user_id=str(membership.user_id),
            role=StudyGroupMemberRole(membership.member_role.value),
            joined_at=membership.joined_at,
        )

    @staticmethod
    def _uuid(value: str, field_name: str) -> UUID:
        """Validate identifiers before passing them to PostgreSQL."""

        try:
            return UUID(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} must be a valid UUID") from exc

    @staticmethod
    def _escape_like(value: str) -> str:
        """Treat SQL LIKE wildcard characters as literal search text."""

        return (
            value.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
