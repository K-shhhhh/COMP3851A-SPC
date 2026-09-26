"""Application use cases for public and private Study Groups.

The service coordinates validation, permissions, membership, and persistence
without depending on FastAPI or SQLAlchemy.
"""

from datetime import datetime, timezone

from app.domains.study_groups.domain.exceptions import (
    InvalidStudyGroupError,
    PrivateStudyGroupJoinError,
    StudyGroupAlreadyMemberError,
    StudyGroupFullError,
    StudyGroupMembershipNotFoundError,
    StudyGroupNotFoundError,
    StudyGroupPermissionDeniedError,
)
from app.domains.study_groups.domain.models import (
    MyGroupsFilter,
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