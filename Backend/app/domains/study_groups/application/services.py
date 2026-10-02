"""Application use cases for public and private Study Groups.

The service coordinates validation, permissions, membership, and persistence
without depending on FastAPI or SQLAlchemy.
"""

from datetime import datetime, timezone

from app.domains.chats.domain.answering import ChatAnswerGenerator
from app.domains.chats.domain.embedding import QuestionEmbeddingProvider
from app.domains.chats.domain.models import ChatSource
from app.domains.chats.domain.retrieval import GroundingChunk
from app.domains.study_groups.domain.exceptions import (
    InvalidStudyGroupMessageError,
    InvalidStudyGroupError,
    PrivateStudyGroupJoinError,
    StudyGroupAlreadyMemberError,
    StudyGroupAiUnavailableError,
    StudyGroupAnswerGenerationError,
    StudyGroupChannelNameConflictError,
    StudyGroupChannelNotFoundError,
    StudyGroupFullError,
    StudyGroupMembershipNotFoundError,
    StudyGroupMentionedUserNotMemberError,
    StudyGroupMessageNotFoundError,
    StudyGroupMessagePermissionDeniedError,
    StudyGroupNotFoundError,
    StudyGroupPermissionDeniedError,
    StudyGroupTargetUserNotFoundError,
    StudyGroupNoReadyChunksError,
)
from app.domains.study_groups.domain.models import (
    MyGroupsFilter,
    StudyGroupAiMode,
    StudyGroupChannel,
    StudyGroupMessage,
    StudyGroupMember,
    StudyGroupMemberRole,
    StudyGroupMembership,
    StudyGroupSummary,
    StudyGroupVisibility,
)
from app.domains.study_groups.domain.repository import (
    StudyGroupRepository,
)
from app.domains.study_groups.domain.retrieval import (
    StudyGroupReadyChunkRepository,
)


class StudyGroupService:
    """Coordinate Study Group business rules and persistence."""

    def __init__(
        self,
        repository: StudyGroupRepository,
        chunk_repository: StudyGroupReadyChunkRepository | None = None,
        answer_generator: ChatAnswerGenerator | None = None,
        question_embedding_provider: QuestionEmbeddingProvider | None = None,
        semantic_search_limit: int = 5,
    ) -> None:
        """Initialize the service with replaceable persistence."""

        if semantic_search_limit <= 0:
            raise ValueError("semantic_search_limit must be positive")

        self._repository = repository
        self._chunk_repository = chunk_repository
        self._answer_generator = answer_generator
        self._question_embedding_provider = question_embedding_provider
        self._semantic_search_limit = semantic_search_limit

    async def discover_public_groups(
        self,
        *,
        user_id: str,
        page: int,
        page_size: int,
        search: str | None,
    ) -> tuple[list[StudyGroupSummary], int]:
        """Return active public groups for the Discover Public page."""

        self._validate_pagination(page=page, page_size=page_size)
        normalized_search = self._normalize_search(search)

        return await self._repository.list_discoverable_public_groups(
            user_id=user_id,
            offset=(page - 1) * page_size,
            limit=page_size,
            search=normalized_search,
        )

    async def list_my_groups(
        self,
        *,
        user_id: str,
        group_filter: MyGroupsFilter,
        page: int,
        page_size: int,
    ) -> tuple[list[StudyGroupSummary], int]:
        """Return groups owned by or joined by the current student."""

        self._validate_pagination(page=page, page_size=page_size)

        return await self._repository.list_user_groups(
            user_id=user_id,
            group_filter=group_filter,
            offset=(page - 1) * page_size,
            limit=page_size,
        )

    async def get_group(
        self,
        *,
        group_id: str,
        user_id: str,
    ) -> StudyGroupSummary:
        """Return a group only when it is visible to the current student."""

        group = await self._repository.get_group_for_user(
            group_id=group_id,
            user_id=user_id,
        )

        if group is None:
            raise StudyGroupNotFoundError("Study group not found.")

        return group

    async def list_members(
        self,
        *,
        group_id: str,
        user_id: str,
        page: int,
        page_size: int,
    ) -> tuple[list[StudyGroupMember], int]:
        """List members only for a student who belongs to the group."""

        self._validate_pagination(page=page, page_size=page_size)
        group = await self._repository.get_group_for_user(
            group_id=group_id,
            user_id=user_id,
        )
        if group is None:
            raise StudyGroupNotFoundError("Study group not found.")
        if not group.is_member:
            raise StudyGroupPermissionDeniedError(
                "You must be a group member to view its members."
            )

        return await self._repository.list_members(
            group_id=group_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )

    async def add_member_by_email(
        self,
        *,
        group_id: str,
        requester_user_id: str,
        email: str,
    ) -> StudyGroupMembership:
        """Allow an owner/admin to add an active student by email."""

        group = await self._get_manageable_group(
            group_id=group_id,
            user_id=requester_user_id,
        )
        target_user_id = (
            await self._repository.find_active_user_id_by_email(
                email=email.strip().casefold()
            )
        )
        if target_user_id is None:
            raise StudyGroupTargetUserNotFoundError(
                "No active student account was found for that email."
            )

        existing = await self._repository.get_membership(
            group_id=group_id,
            user_id=target_user_id,
        )
        if existing is not None:
            raise StudyGroupAlreadyMemberError(
                "That student is already a member of this study group."
            )
        if group.member_count >= group.group.max_members:
            raise StudyGroupFullError(
                "This study group has reached its member limit."
            )

        return await self._repository.create_membership(
            group_id=group_id,
            user_id=target_user_id,
            role=StudyGroupMemberRole.MEMBER,
            joined_at=datetime.now(timezone.utc),
        )

    async def remove_member(
        self,
        *,
        group_id: str,
        requester_user_id: str,
        target_user_id: str,
    ) -> None:
        """Allow an owner/admin to remove an ordinary group member."""

        group = await self._get_manageable_group(
            group_id=group_id,
            user_id=requester_user_id,
        )
        membership = await self._repository.get_membership(
            group_id=group_id,
            user_id=target_user_id,
        )
        if membership is None:
            raise StudyGroupMembershipNotFoundError(
                "That student is not a member of this study group."
            )
        if (
            target_user_id == group.group.created_by
            or target_user_id == group.group.current_admin_id
            or membership.role == StudyGroupMemberRole.ADMIN
        ):
            raise StudyGroupPermissionDeniedError(
                "A group owner or administrator cannot be removed."
            )

        deleted = await self._repository.delete_membership(
            group_id=group_id,
            user_id=target_user_id,
        )
        if not deleted:
            raise StudyGroupMembershipNotFoundError(
                "That student is not a member of this study group."
            )

    async def list_channels(
        self,
        *,
        group_id: str,
        user_id: str,
        page: int,
        page_size: int,
    ) -> tuple[list[StudyGroupChannel], int]:
        """List channels for an active member of the group."""

        self._validate_pagination(page=page, page_size=page_size)
        await self._get_member_group(group_id=group_id, user_id=user_id)
        return await self._repository.list_channels(
            group_id=group_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )

    async def get_channel(
        self,
        *,
        group_id: str,
        channel_id: str,
        user_id: str,
    ) -> StudyGroupChannel:
        """Return a channel only to an active group member."""

        await self._get_member_group(group_id=group_id, user_id=user_id)
        channel = await self._repository.get_channel(
            group_id=group_id,
            channel_id=channel_id,
        )
        if channel is None:
            raise StudyGroupChannelNotFoundError(
                "Study group channel not found."
            )
        return channel

    async def create_channel(
        self,
        *,
        group_id: str,
        user_id: str,
        name: str,
        description: str | None,
    ) -> StudyGroupChannel:
        """Create an admin-named channel as a group owner/admin."""

        await self._get_manageable_group(group_id=group_id, user_id=user_id)
        normalized_name = self._normalize_channel_name(name)
        normalized_description = self._normalize_channel_description(
            description
        )
        if await self._repository.channel_name_exists(
            group_id=group_id,
            normalized_name=normalized_name,
        ):
            raise StudyGroupChannelNameConflictError(
                "An active channel with that name already exists."
            )
        now = datetime.now(timezone.utc)
        return await self._repository.create_channel(
            group_id=group_id,
            name=normalized_name,
            description=normalized_description,
            created_by=user_id,
            created_at=now,
        )

    async def update_channel(
        self,
        *,
        group_id: str,
        channel_id: str,
        user_id: str,
        name: str,
        description: str | None,
    ) -> StudyGroupChannel:
        """Update a channel as a group owner/admin."""

        await self._get_manageable_group(group_id=group_id, user_id=user_id)
        existing = await self._repository.get_channel(
            group_id=group_id,
            channel_id=channel_id,
        )
        if existing is None:
            raise StudyGroupChannelNotFoundError(
                "Study group channel not found."
            )
        normalized_name = self._normalize_channel_name(name)
        normalized_description = self._normalize_channel_description(
            description
        )
        if await self._repository.channel_name_exists(
            group_id=group_id,
            normalized_name=normalized_name,
            exclude_channel_id=channel_id,
        ):
            raise StudyGroupChannelNameConflictError(
                "An active channel with that name already exists."
            )
        return await self._repository.update_channel(
            group_id=group_id,
            channel_id=channel_id,
            name=normalized_name,
            description=normalized_description,
            updated_at=datetime.now(timezone.utc),
        )

    async def delete_channel(
        self,
        *,
        group_id: str,
        channel_id: str,
        user_id: str,
    ) -> None:
        """Soft-delete a channel as a group owner/admin."""

        await self._get_manageable_group(group_id=group_id, user_id=user_id)
        deleted = await self._repository.soft_delete_channel(
            group_id=group_id,
            channel_id=channel_id,
            deleted_at=datetime.now(timezone.utc),
        )
        if not deleted:
            raise StudyGroupChannelNotFoundError(
                "Study group channel not found."
            )

    async def list_messages(
        self,
        *,
        group_id: str,
        channel_id: str,
        user_id: str,
        page: int,
        page_size: int,
    ) -> tuple[list[StudyGroupMessage], int]:
        """List active messages for a member of the owning group."""

        self._validate_pagination(page=page, page_size=page_size)
        await self._get_member_channel(
            group_id=group_id,
            channel_id=channel_id,
            user_id=user_id,
        )
        return await self._repository.list_messages(
            group_id=group_id,
            channel_id=channel_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )

    async def get_message(
        self,
        *,
        group_id: str,
        channel_id: str,
        message_id: int,
        user_id: str,
    ) -> StudyGroupMessage:
        """Return one active message to a member of the owning group."""

        await self._get_member_channel(
            group_id=group_id,
            channel_id=channel_id,
            user_id=user_id,
        )
        message = await self._repository.get_message(
            group_id=group_id,
            channel_id=channel_id,
            message_id=message_id,
        )
        if message is None:
            raise StudyGroupMessageNotFoundError(
                "Study group message not found."
            )
        return message

    async def create_message(
        self,
        *,
        group_id: str,
        channel_id: str,
        user_id: str,
        content: str,
        mentioned_user_ids: list[str] | None = None,
        ai_mode: StudyGroupAiMode | None = None,
        response_format: str | None = None,
    ) -> StudyGroupMessage:
        """Create a member message and optionally generate a companion reply."""

        await self._get_member_channel(
            group_id=group_id,
            channel_id=channel_id,
            user_id=user_id,
        )
        normalized_content = self._normalize_message_content(content)
        normalized_mentions = await self._normalize_mentioned_user_ids(
            group_id=group_id,
            mentioned_user_ids=mentioned_user_ids,
        )

        chunks: tuple[GroundingChunk, ...] = ()
        if ai_mode is not None:
            if (
                self._chunk_repository is None
                or self._answer_generator is None
            ):
                raise StudyGroupAiUnavailableError(
                    "Group companion services are not configured."
                )
            if self._question_embedding_provider is None:
                chunks = (
                    await self._chunk_repository.list_ready_chunks_for_channel(
                        group_id=group_id,
                        channel_id=channel_id,
                    )
                )
            else:
                query_embedding = (
                    await self._question_embedding_provider.embed_question(
                        normalized_content
                    )
                )
                chunks = (
                    await self._chunk_repository.search_ready_chunks_for_channel(
                        group_id=group_id,
                        channel_id=channel_id,
                        query_embedding=query_embedding,
                        limit=self._semantic_search_limit,
                    )
                )
            if not chunks:
                raise StudyGroupNoReadyChunksError(
                    "Upload and process at least one attachment in this "
                    "channel before mentioning a companion."
                )
        elif response_format is not None:
            raise InvalidStudyGroupMessageError(
                "response_format requires an AI companion mode."
            )

        message = await self._repository.create_message(
            group_id=group_id,
            channel_id=channel_id,
            author_id=user_id,
            content=normalized_content,
            mentioned_user_ids=normalized_mentions,
            ai_mode=ai_mode,
            sent_at=datetime.now(timezone.utc),
        )

        if ai_mode is None:
            return message

        try:
            answer = await self._answer_generator.answer_question(
                question=normalized_content,
                chunks=chunks,
                response_format=response_format,
                mode=ai_mode.value,
            )
            self._validate_ai_sources(answer.sources, chunks)
            return await self._repository.save_ai_response(
                group_id=group_id,
                channel_id=channel_id,
                message_id=message.message_id,
                mode=ai_mode,
                content=answer.content.strip(),
                sources=answer.sources,
                generated_at=datetime.now(timezone.utc),
            )
        except Exception as exc:
            raise StudyGroupAnswerGenerationError(
                "The selected group companion could not generate a response."
            ) from exc

    async def update_message(
        self,
        *,
        group_id: str,
        channel_id: str,
        message_id: int,
        user_id: str,
        content: str,
        mentioned_user_ids: list[str] | None = None,
    ) -> StudyGroupMessage:
        """Edit a normal message only when the requester is its author."""

        await self._get_member_channel(
            group_id=group_id,
            channel_id=channel_id,
            user_id=user_id,
        )
        message = await self._repository.get_message(
            group_id=group_id,
            channel_id=channel_id,
            message_id=message_id,
        )
        if message is None:
            raise StudyGroupMessageNotFoundError(
                "Study group message not found."
            )
        if message.author_id != user_id:
            raise StudyGroupMessagePermissionDeniedError(
                "You can only edit your own messages."
            )
        if message.ai_mode_used is not None:
            raise StudyGroupMessagePermissionDeniedError(
                "Messages that invoked an AI companion cannot be edited."
            )

        normalized_content = self._normalize_message_content(content)
        normalized_mentions = await self._normalize_mentioned_user_ids(
            group_id=group_id,
            mentioned_user_ids=mentioned_user_ids,
        )
        return await self._repository.update_message(
            group_id=group_id,
            channel_id=channel_id,
            message_id=message_id,
            content=normalized_content,
            mentioned_user_ids=normalized_mentions,
            edited_at=datetime.now(timezone.utc),
        )

    async def delete_message(
        self,
        *,
        group_id: str,
        channel_id: str,
        message_id: int,
        user_id: str,
    ) -> None:
        """Soft-delete a normal message only when requester is its author."""

        await self._get_member_channel(
            group_id=group_id,
            channel_id=channel_id,
            user_id=user_id,
        )
        message = await self._repository.get_message(
            group_id=group_id,
            channel_id=channel_id,
            message_id=message_id,
        )
        if message is None:
            raise StudyGroupMessageNotFoundError(
                "Study group message not found."
            )
        if message.author_id != user_id:
            raise StudyGroupMessagePermissionDeniedError(
                "You can only delete your own messages."
            )

        deleted = await self._repository.soft_delete_message(
            group_id=group_id,
            channel_id=channel_id,
            message_id=message_id,
            deleted_at=datetime.now(timezone.utc),
        )
        if not deleted:
            raise StudyGroupMessageNotFoundError(
                "Study group message not found."
            )

    async def create_group(
        self,
        *,
        user_id: str,
        name: str,
        description: str | None,
        visibility: StudyGroupVisibility,
        max_members: int,
    ) -> StudyGroupSummary:
        """Create a group owned and administered by the current student."""

        normalized_name = self._normalize_name(name)
        normalized_description = self._normalize_description(description)
        self._validate_max_members(max_members)

        # The repository creates both the group and the creator's admin
        # membership in one transaction.
        return await self._repository.create_group(
            name=normalized_name,
            description=normalized_description,
            visibility=visibility,
            created_by=user_id,
            max_members=max_members,
        )

    async def update_group(
        self,
        *,
        group_id: str,
        user_id: str,
        name: str,
        description: str | None,
        visibility: StudyGroupVisibility,
        max_members: int,
    ) -> StudyGroupSummary:
        """Update a group after checking admin permission."""

        existing = await self._get_manageable_group(
            group_id=group_id,
            user_id=user_id,
        )

        normalized_name = self._normalize_name(name)
        normalized_description = self._normalize_description(description)
        self._validate_max_members(max_members)

        if max_members < existing.member_count:
            raise InvalidStudyGroupError(
                "Maximum members cannot be lower than the current member count."
            )

        await self._repository.update_group(
            group_id=group_id,
            name=normalized_name,
            description=normalized_description,
            visibility=visibility,
            max_members=max_members,
            updated_at=datetime.now(timezone.utc),
        )

        updated = await self._repository.get_group_for_user(
            group_id=group_id,
            user_id=user_id,
        )

        if updated is None:
            raise StudyGroupNotFoundError("Study group not found.")

        return updated

    async def delete_group(
        self,
        *,
        group_id: str,
        user_id: str,
    ) -> None:
        """Soft-delete a group after checking admin permission."""

        await self._get_manageable_group(
            group_id=group_id,
            user_id=user_id,
        )

        deleted = await self._repository.soft_delete_group(
            group_id=group_id,
            deleted_at=datetime.now(timezone.utc),
        )

        if not deleted:
            raise StudyGroupNotFoundError("Study group not found.")

    async def join_public_group(
        self,
        *,
        group_id: str,
        user_id: str,
    ) -> StudyGroupSummary:
        """Add the current student to an active public group."""

        group = await self._repository.get_group(group_id=group_id)

        if group is None:
            raise StudyGroupNotFoundError("Study group not found.")

        if group.visibility != StudyGroupVisibility.PUBLIC:
            raise PrivateStudyGroupJoinError(
                "Private groups require an invitation from an administrator."
            )

        existing_membership = await self._repository.get_membership(
            group_id=group_id,
            user_id=user_id,
        )

        if existing_membership is not None:
            raise StudyGroupAlreadyMemberError(
                "You are already a member of this study group."
            )

        member_count = await self._repository.count_members(
            group_id=group_id,
        )

        if member_count >= group.max_members:
            raise StudyGroupFullError(
                "This study group has reached its member limit."
            )

        await self._repository.create_membership(
            group_id=group_id,
            user_id=user_id,
            role=StudyGroupMemberRole.MEMBER,
            joined_at=datetime.now(timezone.utc),
        )

        joined_group = await self._repository.get_group_for_user(
            group_id=group_id,
            user_id=user_id,
        )

        if joined_group is None:
            raise StudyGroupNotFoundError("Study group not found.")

        return joined_group

    async def leave_group(
        self,
        *,
        group_id: str,
        user_id: str,
    ) -> None:
        """Remove the current student's active membership."""

        group = await self.get_group(
            group_id=group_id,
            user_id=user_id,
        )

        membership = await self._repository.get_membership(
            group_id=group_id,
            user_id=user_id,
        )

        if membership is None:
            raise StudyGroupMembershipNotFoundError(
                "You are not a member of this study group."
            )

        # An administrator must transfer responsibility or delete the group.
        if (
            group.is_owner
            or membership.role == StudyGroupMemberRole.ADMIN
        ):
            raise StudyGroupPermissionDeniedError(
                "A group administrator cannot leave before transferring "
                "administration or deleting the group."
            )

        deleted = await self._repository.delete_membership(
            group_id=group_id,
            user_id=user_id,
        )

        if not deleted:
            raise StudyGroupMembershipNotFoundError(
                "You are not a member of this study group."
            )

    async def _get_manageable_group(
        self,
        *,
        group_id: str,
        user_id: str,
    ) -> StudyGroupSummary:
        """Return a group only when the current student may manage it."""

        group = await self._repository.get_group_for_user(
            group_id=group_id,
            user_id=user_id,
        )

        if group is None:
            raise StudyGroupNotFoundError("Study group not found.")

        can_manage = (
            group.is_owner
            or group.membership_role == StudyGroupMemberRole.ADMIN
        )

        if not can_manage:
            raise StudyGroupPermissionDeniedError(
                "You do not have permission to manage this study group."
            )

        return group

    async def _get_member_group(
        self,
        *,
        group_id: str,
        user_id: str,
    ) -> StudyGroupSummary:
        """Return a group only when the student is an active member."""

        group = await self._repository.get_group_for_user(
            group_id=group_id,
            user_id=user_id,
        )
        if group is None:
            raise StudyGroupNotFoundError("Study group not found.")
        if not group.is_member:
            raise StudyGroupPermissionDeniedError(
                "You must join the group before accessing its content."
            )
        return group

    async def _get_member_channel(
        self,
        *,
        group_id: str,
        channel_id: str,
        user_id: str,
    ) -> StudyGroupChannel:
        """Return a channel only to an active member of its owning group."""

        await self._get_member_group(group_id=group_id, user_id=user_id)
        channel = await self._repository.get_channel(
            group_id=group_id,
            channel_id=channel_id,
        )
        if channel is None:
            raise StudyGroupChannelNotFoundError(
                "Study group channel not found."
            )
        return channel

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normalize and validate a group display name."""

        normalized = " ".join(name.split())

        if not normalized:
            raise InvalidStudyGroupError(
                "Study group name must not be empty."
            )

        if len(normalized) > 100:
            raise InvalidStudyGroupError(
                "Study group name must not exceed 100 characters."
            )

        return normalized

    @staticmethod
    def _normalize_description(
        description: str | None,
    ) -> str | None:
        """Normalize an optional group description."""

        if description is None:
            return None

        normalized = description.strip()

        if not normalized:
            return None

        if len(normalized) > 1000:
            raise InvalidStudyGroupError(
                "Study group description must not exceed 1000 characters."
            )

        return normalized

    @staticmethod
    def _normalize_channel_name(name: str) -> str:
        """Normalize an administrator-supplied channel name."""

        normalized = " ".join(name.split())
        if not normalized:
            raise InvalidStudyGroupError(
                "Channel name must not be empty."
            )
        if len(normalized) > 100:
            raise InvalidStudyGroupError(
                "Channel name must not exceed 100 characters."
            )
        return normalized

    @staticmethod
    def _normalize_channel_description(
        description: str | None,
    ) -> str | None:
        """Normalize an optional channel description."""

        if description is None:
            return None
        normalized = description.strip()
        if not normalized:
            return None
        if len(normalized) > 1000:
            raise InvalidStudyGroupError(
                "Channel description must not exceed 1000 characters."
            )
        return normalized

    @staticmethod
    def _normalize_message_content(content: str) -> str:
        """Normalize surrounding whitespace and validate message content."""

        normalized = content.strip()
        if not normalized:
            raise InvalidStudyGroupMessageError(
                "Message content must not be empty."
            )
        if len(normalized) > 4000:
            raise InvalidStudyGroupMessageError(
                "Message content must not exceed 4000 characters."
            )
        return normalized

    async def _normalize_mentioned_user_ids(
        self,
        *,
        group_id: str,
        mentioned_user_ids: list[str] | None,
    ) -> tuple[str, ...]:
        """Validate and normalize structured human mentions.

        The frontend supplies stable user identifiers selected from the group
        member list. Raw display names inside message text are not trusted for
        authorization or notification delivery.
        """

        unique_ids: list[str] = []
        seen: set[str] = set()
        for raw_user_id in mentioned_user_ids or []:
            user_id = raw_user_id.strip()
            if not user_id:
                raise InvalidStudyGroupMessageError(
                    "Mentioned user identifiers must not be empty."
                )
            if user_id not in seen:
                seen.add(user_id)
                unique_ids.append(user_id)

        if len(unique_ids) > 20:
            raise InvalidStudyGroupMessageError(
                "A message must not mention more than 20 users."
            )

        for mentioned_user_id in unique_ids:
            membership = await self._repository.get_membership(
                group_id=group_id,
                user_id=mentioned_user_id,
            )
            if membership is None:
                raise StudyGroupMentionedUserNotMemberError(
                    "Every mentioned user must be an active member of the "
                    "same study group."
                )

        return tuple(unique_ids)

    @staticmethod
    def _validate_ai_sources(
        sources: tuple[ChatSource, ...],
        chunks: tuple[GroundingChunk, ...],
    ) -> None:
        """Reject citations outside the authorized group-channel chunks."""

        allowed_sources = {chunk.source for chunk in chunks}
        if any(source not in allowed_sources for source in sources):
            raise ValueError(
                "AI response cited a source outside the authorized channel."
            )

    @staticmethod
    def _normalize_search(search: str | None) -> str | None:
        """Normalize the optional Discover Public search value."""

        if search is None:
            return None

        normalized = " ".join(search.split())

        if not normalized:
            return None

        if len(normalized) > 100:
            raise InvalidStudyGroupError(
                "Search text must not exceed 100 characters."
            )

        return normalized

    @staticmethod
    def _validate_max_members(max_members: int) -> None:
        """Require a positive member limit."""

        if max_members <= 0:
            raise InvalidStudyGroupError(
                "Maximum members must be greater than zero."
            )

    @staticmethod
    def _validate_pagination(
        *,
        page: int,
        page_size: int,
    ) -> None:
        """Validate application-level pagination values."""

        if page <= 0:
            raise InvalidStudyGroupError(
                "Page must be greater than zero."
            )

        if page_size <= 0 or page_size > 100:
            raise InvalidStudyGroupError(
                "Page size must be between 1 and 100."
            )
