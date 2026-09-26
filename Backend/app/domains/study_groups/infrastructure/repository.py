"""PostgreSQL persistence for collaborative Study Group use cases.

The adapter maps SQLAlchemy rows into framework-independent domain objects.
It also repeats concurrency-sensitive membership and capacity rules inside the
database transaction so simultaneous requests cannot bypass them.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.domains.study_groups.domain.repository import StudyGroupRepository
from app.models.orm_models import (
    Group as ORMGroup,
    GroupType,
    MemberRole,
    Membership as ORMMembership,
)


class PostgreSQLStudyGroupRepository(StudyGroupRepository):
    """Store study groups and memberships in PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        """Use the request-scoped SQLAlchemy session."""

        self._session = session

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
            statement = statement.with_for_update()
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
