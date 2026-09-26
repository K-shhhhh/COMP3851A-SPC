"""Persistence contract for Study Group use cases.

The application layer depends on this interface instead of depending directly
on PostgreSQL or an in-memory implementation.
"""

from abc import ABC, abstractmethod
from datetime import datetime

from app.domains.study_groups.domain.models import (
    MyGroupsFilter,
    StudyGroup,
    StudyGroupChannel,
    StudyGroupMember,
    StudyGroupMemberRole,
    StudyGroupMembership,
    StudyGroupSummary,
    StudyGroupVisibility,
)


class StudyGroupRepository(ABC):
    """Define storage operations required by Study Group use cases."""

    @abstractmethod
    async def list_discoverable_public_groups(
        self,
        *,
        user_id: str,
        offset: int,
        limit: int,
        search: str | None = None,
    ) -> tuple[list[StudyGroupSummary], int]:
        """Return active public groups visible in Discover Public.

        The result includes whether the current user has already joined each
        group. Private and personal groups must never be returned.
        """

        raise NotImplementedError

    @abstractmethod
    async def list_user_groups(
        self,
        *,
        user_id: str,
        group_filter: MyGroupsFilter,
        offset: int,
        limit: int,
    ) -> tuple[list[StudyGroupSummary], int]:
        """Return active groups owned by or joined by the current user."""

        raise NotImplementedError

    @abstractmethod
    async def get_group_for_user(
        self,
        *,
        group_id: str,
        user_id: str,
    ) -> StudyGroupSummary | None:
        """Return a group when it is visible to the current user.

        Public groups are visible to authenticated students. Private groups are
        visible only to active members.
        """

        raise NotImplementedError

    @abstractmethod
    async def get_group(
        self,
        *,
        group_id: str,
    ) -> StudyGroup | None:
        """Return one active public or private group without user projection."""

        raise NotImplementedError

    @abstractmethod
    async def find_active_user_id_by_email(
        self,
        *,
        email: str,
    ) -> str | None:
        """Find an active student account using a normalized email address.

        This allows an owner or administrator to add a member using an email
        address instead of requiring the frontend to know the student's UUID.

        The implementation must exclude deactivated and soft-deleted users.
        """

        raise NotImplementedError

    @abstractmethod
    async def list_members(
        self,
        *,
        group_id: str,
        offset: int,
        limit: int,
    ) -> tuple[list[StudyGroupMember], int]:
        """Return a paginated list of members belonging to one active group.

        The returned projection contains only safe public profile information
        together with the membership role and joining time.
        """

        raise NotImplementedError

    @abstractmethod
    async def create_group(
        self,
        *,
        name: str,
        description: str | None,
        visibility: StudyGroupVisibility,
        created_by: str,
        max_members: int,
    ) -> StudyGroupSummary:
        """Create a group and its initial admin membership atomically.

        The `created_by` student becomes both the owner and the first admin.
        """

        raise NotImplementedError

    @abstractmethod
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
        """Update an active group after authorization has been checked."""

        raise NotImplementedError

    @abstractmethod
    async def soft_delete_group(
        self,
        *,
        group_id: str,
        deleted_at: datetime,
    ) -> bool:
        """Soft-delete an active group.

        Return `False` if an active group with that identifier does not exist.
        """

        raise NotImplementedError

    @abstractmethod
    async def get_membership(
        self,
        *,
        group_id: str,
        user_id: str,
    ) -> StudyGroupMembership | None:
        """Return the active membership between a user and group."""

        raise NotImplementedError

    @abstractmethod
    async def create_membership(
        self,
        *,
        group_id: str,
        user_id: str,
        role: StudyGroupMemberRole,
        joined_at: datetime,
    ) -> StudyGroupMembership:
        """Create an active membership.

        The PostgreSQL implementation must preserve the unique user/group
        membership constraint.
        """

        raise NotImplementedError

    @abstractmethod
    async def delete_membership(
        self,
        *,
        group_id: str,
        user_id: str,
    ) -> bool:
        """Hard-delete an active membership when a student leaves."""

        raise NotImplementedError

    @abstractmethod
    async def count_members(
        self,
        *,
        group_id: str,
    ) -> int:
        """Return the number of active memberships in one group."""

        raise NotImplementedError

    @abstractmethod
    async def list_channels(
        self,
        *,
        group_id: str,
        offset: int,
        limit: int,
    ) -> tuple[list[StudyGroupChannel], int]:
        """Return active channels belonging to one active study group."""

        raise NotImplementedError

    @abstractmethod
    async def get_channel(
        self,
        *,
        group_id: str,
        channel_id: str,
    ) -> StudyGroupChannel | None:
        """Return one active channel belonging to the specified group."""

        raise NotImplementedError

    @abstractmethod
    async def channel_name_exists(
        self,
        *,
        group_id: str,
        normalized_name: str,
        exclude_channel_id: str | None = None,
    ) -> bool:
        """Check active channel-name uniqueness within one group."""

        raise NotImplementedError

    @abstractmethod
    async def create_channel(
        self,
        *,
        group_id: str,
        name: str,
        description: str | None,
        created_by: str,
        created_at: datetime,
    ) -> StudyGroupChannel:
        """Create a named channel after application authorization."""

        raise NotImplementedError

    @abstractmethod
    async def update_channel(
        self,
        *,
        group_id: str,
        channel_id: str,
        name: str,
        description: str | None,
        updated_at: datetime,
    ) -> StudyGroupChannel:
        """Replace editable fields on an active group channel."""

        raise NotImplementedError

    @abstractmethod
    async def soft_delete_channel(
        self,
        *,
        group_id: str,
        channel_id: str,
        deleted_at: datetime,
    ) -> bool:
        """Soft-delete a channel and report whether it existed."""

        raise NotImplementedError
