"""Application use cases for public and private Study Groups.

The service coordinates validation, permissions, membership, and persistence
without depending on FastAPI or SQLAlchemy.
"""

from datetime import datetime, timezone

from app.domains.study_groups.domain.exceptions import (
    InvalidStudyGroupError,
    PrivateStudyGroupJoinError,
    StudyGroupAlreadyMemberError,
    StudyGroupChannelNameConflictError,
    StudyGroupChannelNotFoundError,
    StudyGroupFullError,
    StudyGroupMembershipNotFoundError,
    StudyGroupNotFoundError,
    StudyGroupPermissionDeniedError,
    StudyGroupTargetUserNotFoundError,
)
from app.domains.study_groups.domain.models import (
    MyGroupsFilter,
    StudyGroupChannel,
    StudyGroupMember,
    StudyGroupMemberRole,
    StudyGroupMembership,
    StudyGroupSummary,
    StudyGroupVisibility,
)
from app.domains.study_groups.domain.repository import (
    StudyGroupRepository,
)


class StudyGroupService:
    """Coordinate Study Group business rules and persistence."""

    def __init__(self, repository: StudyGroupRepository) -> None:
        """Initialize the service with replaceable persistence."""

        self._repository = repository

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
                "You must join the group before accessing its channels."
            )
        return group

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
