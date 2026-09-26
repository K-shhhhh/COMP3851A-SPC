"""In-memory Study Group persistence for isolated tests and local development."""

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from itertools import count
from uuid import uuid4

from app.domains.study_groups.domain.exceptions import (
    InvalidStudyGroupError,
    StudyGroupAlreadyMemberError,
    StudyGroupFullError,
)
from app.domains.study_groups.domain.models import (
    MyGroupsFilter,
    StudyGroup,
    StudyGroupMemberRole,
    StudyGroupMembership,
    StudyGroupSummary,
    StudyGroupVisibility,
)
from app.domains.study_groups.domain.repository import (
    StudyGroupRepository,
)


class InMemoryStudyGroupRepository(StudyGroupRepository):
    """Store Study Groups and memberships inside one backend process."""

    def __init__(self) -> None:
        """Initialize empty group and membership collections."""

        self._groups: dict[str, StudyGroup] = {}

        # One active membership is stored for each user/group combination.
        self._memberships: dict[
            tuple[str, str],
            StudyGroupMembership,
        ] = {}

        self._membership_ids = count(start=1)
        self._lock = asyncio.Lock()

    async def list_discoverable_public_groups(
        self,
        *,
        user_id: str,
        offset: int,
        limit: int,
        search: str | None = None,
    ) -> tuple[list[StudyGroupSummary], int]:
        """Return active public groups, including membership information."""

        self._validate_pagination(offset=offset, limit=limit)

        async with self._lock:
            groups = [
                group
                for group in self._groups.values()
                if (
                    group.deleted_at is None
                    and group.visibility == StudyGroupVisibility.PUBLIC
                    and self._matches_search(group, search)
                )
            ]

            groups.sort(
                key=lambda group: group.updated_at,
                reverse=True,
            )

            total = len(groups)
            page = groups[offset : offset + limit]

            return (
                [
                    self._to_summary(
                        group=group,
                        user_id=user_id,
                    )
                    for group in page
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
        """Return active groups owned by or joined by one student."""

        self._validate_pagination(offset=offset, limit=limit)

        async with self._lock:
            groups: list[StudyGroup] = []

            for group in self._groups.values():
                if group.deleted_at is not None:
                    continue

                membership = self._memberships.get(
                    (group.group_id, user_id)
                )

                is_owner = group.created_by == user_id
                is_member = membership is not None

                if not is_owner and not is_member:
                    continue

                if (
                    group_filter == MyGroupsFilter.PUBLIC
                    and group.visibility != StudyGroupVisibility.PUBLIC
                ):
                    continue

                if (
                    group_filter == MyGroupsFilter.PRIVATE
                    and group.visibility != StudyGroupVisibility.PRIVATE
                ):
                    continue

                if (
                    group_filter == MyGroupsFilter.OWNED
                    and not is_owner
                ):
                    continue

                groups.append(group)

            groups.sort(
                key=lambda group: group.updated_at,
                reverse=True,
            )

            total = len(groups)
            page = groups[offset : offset + limit]

            return (
                [
                    self._to_summary(
                        group=group,
                        user_id=user_id,
                    )
                    for group in page
                ],
                total,
            )

    async def get_group_for_user(
        self,
        *,
        group_id: str,
        user_id: str,
    ) -> StudyGroupSummary | None:
        """Return a public group or a private group accessible to the user."""

        async with self._lock:
            group = self._active_group(group_id)

            if group is None:
                return None

            membership = self._memberships.get(
                (group_id, user_id)
            )

            is_owner = group.created_by == user_id

            # Private groups must not be exposed to unrelated students.
            if (
                group.visibility == StudyGroupVisibility.PRIVATE
                and membership is None
                and not is_owner
            ):
                return None

            return self._to_summary(
                group=group,
                user_id=user_id,
            )

    async def get_group(
        self,
        *,
        group_id: str,
    ) -> StudyGroup | None:
        """Return one active group without applying user visibility."""

        async with self._lock:
            return self._active_group(group_id)

    async def create_group(
        self,
        *,
        name: str,
        description: str | None,
        visibility: StudyGroupVisibility,
        created_by: str,
        max_members: int,
    ) -> StudyGroupSummary:
        """Create a group and initial admin membership atomically."""

        async with self._lock:
            now = datetime.now(timezone.utc)
            group_id = str(uuid4())

            group = StudyGroup(
                group_id=group_id,
                name=name,
                visibility=visibility,
                description=description,
                created_by=created_by,
                current_admin_id=created_by,
                max_members=max_members,
                created_at=now,
                updated_at=now,
            )

            membership = StudyGroupMembership(
                membership_id=next(self._membership_ids),
                group_id=group_id,
                user_id=created_by,
                role=StudyGroupMemberRole.ADMIN,
                joined_at=now,
            )

            self._groups[group_id] = group
            self._memberships[(group_id, created_by)] = membership

            return self._to_summary(
                group=group,
                user_id=created_by,
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

        async with self._lock:
            group = self._active_group(group_id)

            if group is None:
                raise LookupError("Study group not found.")

            member_count = self._count_members_unlocked(group_id)

            if max_members < member_count:
                raise InvalidStudyGroupError(
                    "Maximum members cannot be lower than "
                    "the current member count."
                )

            updated = replace(
                group,
                name=name,
                description=description,
                visibility=visibility,
                max_members=max_members,
                updated_at=updated_at,
            )

            self._groups[group_id] = updated
            return updated

    async def soft_delete_group(
        self,
        *,
        group_id: str,
        deleted_at: datetime,
    ) -> bool:
        """Mark an active group as deleted without removing its records."""

        async with self._lock:
            group = self._active_group(group_id)

            if group is None:
                return False

            self._groups[group_id] = replace(
                group,
                deleted_at=deleted_at,
                updated_at=deleted_at,
            )

            return True

    async def get_membership(
        self,
        *,
        group_id: str,
        user_id: str,
    ) -> StudyGroupMembership | None:
        """Return an active membership for one user and group."""

        async with self._lock:
            if self._active_group(group_id) is None:
                return None

            return self._memberships.get(
                (group_id, user_id)
            )

    async def create_membership(
        self,
        *,
        group_id: str,
        user_id: str,
        role: StudyGroupMemberRole,
        joined_at: datetime,
    ) -> StudyGroupMembership:
        """Create membership while enforcing uniqueness and capacity."""

        async with self._lock:
            group = self._active_group(group_id)

            if group is None:
                raise LookupError("Study group not found.")

            key = (group_id, user_id)

            if key in self._memberships:
                raise StudyGroupAlreadyMemberError(
                    "You are already a member of this study group."
                )

            member_count = self._count_members_unlocked(group_id)

            if member_count >= group.max_members:
                raise StudyGroupFullError(
                    "This study group has reached its member limit."
                )

            membership = StudyGroupMembership(
                membership_id=next(self._membership_ids),
                group_id=group_id,
                user_id=user_id,
                role=role,
                joined_at=joined_at,
            )

            self._memberships[key] = membership
            return membership

    async def delete_membership(
        self,
        *,
        group_id: str,
        user_id: str,
    ) -> bool:
        """Hard-delete an active membership."""

        async with self._lock:
            key = (group_id, user_id)

            if key not in self._memberships:
                return False

            del self._memberships[key]
            return True

    async def count_members(
        self,
        *,
        group_id: str,
    ) -> int:
        """Count active memberships in one active group."""

        async with self._lock:
            if self._active_group(group_id) is None:
                return 0

            return self._count_members_unlocked(group_id)

    def _to_summary(
        self,
        *,
        group: StudyGroup,
        user_id: str,
    ) -> StudyGroupSummary:
        """Create a user-scoped group projection.

        This helper is synchronous because callers already hold the repository
        lock.
        """

        membership = self._memberships.get(
            (group.group_id, user_id)
        )

        return StudyGroupSummary(
            group=group,
            member_count=self._count_members_unlocked(
                group.group_id
            ),
            is_member=membership is not None,
            is_owner=group.created_by == user_id,
            membership_role=(
                membership.role
                if membership is not None
                else None
            ),
        )

    def _active_group(
        self,
        group_id: str,
    ) -> StudyGroup | None:
        """Return a group only when it has not been soft-deleted."""

        group = self._groups.get(group_id)

        if group is None or group.deleted_at is not None:
            return None

        return group

    def _count_members_unlocked(
        self,
        group_id: str,
    ) -> int:
        """Count memberships while the caller holds the lock."""

        return sum(
            1
            for membership in self._memberships.values()
            if membership.group_id == group_id
        )

    @staticmethod
    def _matches_search(
        group: StudyGroup,
        search: str | None,
    ) -> bool:
        """Match optional discovery text against name and description."""

        if search is None:
            return True

        search_value = search.casefold()

        return (
            search_value in group.name.casefold()
            or (
                group.description is not None
                and search_value in group.description.casefold()
            )
        )

    @staticmethod
    def _validate_pagination(
        *,
        offset: int,
        limit: int,
    ) -> None:
        """Reject invalid repository pagination."""

        if offset < 0:
            raise ValueError("offset must not be negative")

        if limit <= 0:
            raise ValueError("limit must be greater than zero")