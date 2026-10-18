"""PostgreSQL queries supporting privacy-aware group presence."""

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.presence.domain.exceptions import (
    PresenceUserNotFoundError,
)
from app.domains.presence.domain.models import OnlineGroupMember
from app.domains.presence.domain.repository import PresenceRepository
from app.domains.study_groups.domain.models import StudyGroupMemberRole
from app.models.orm_models import (
    ActivityStatus,
    Group as ORMGroup,
    GroupType,
    Membership as ORMMembership,
    User as ORMUser,
)


class PostgreSQLPresenceRepository(PresenceRepository):
    """Persist preferences and return authorized online-member profiles."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _uuid(value: str) -> UUID:
        """Convert a public UUID string into a PostgreSQL UUID value."""

        try:
            return UUID(value)
        except (TypeError, ValueError) as exc:
            raise PresenceUserNotFoundError(
                "The active user could not be found."
            ) from exc

    async def get_show_online_status(self, user_id: str) -> bool:
        """Return the privacy preference for an active account."""

        statement = select(ORMUser.show_online_status).where(
            ORMUser.user_id == self._uuid(user_id),
            ORMUser.status == ActivityStatus.ACTIVE,
            ORMUser.deleted_at.is_(None),
        )

        result = await self._session.execute(statement)
        preference = result.scalar_one_or_none()

        if preference is None:
            raise PresenceUserNotFoundError(
                "The active user could not be found."
            )

        return bool(preference)

    async def set_show_online_status(
        self,
        *,
        user_id: str,
        enabled: bool,
    ) -> bool:
        """Update the privacy preference for an active account."""

        statement = (
            update(ORMUser)
            .where(
                ORMUser.user_id == self._uuid(user_id),
                ORMUser.status == ActivityStatus.ACTIVE,
                ORMUser.deleted_at.is_(None),
            )
            .values(show_online_status=enabled)
            .returning(ORMUser.show_online_status)
        )

        try:
            result = await self._session.execute(statement)
            updated = result.scalar_one_or_none()

            if updated is None:
                raise PresenceUserNotFoundError(
                    "The active user could not be found."
                )

            await self._session.commit()
            return bool(updated)

        except Exception:
            await self._session.rollback()
            raise

    async def is_active_group_member(
        self,
        *,
        group_id: str,
        user_id: str,
    ) -> bool:
        """Return whether the requester belongs to an active study group."""

        statement = (
            select(ORMMembership.membership_id)
            .join(
                ORMGroup,
                ORMGroup.group_id == ORMMembership.group_id,
            )
            .join(
                ORMUser,
                ORMUser.user_id == ORMMembership.user_id,
            )
            .where(
                ORMMembership.group_id == self._uuid(group_id),
                ORMMembership.user_id == self._uuid(user_id),
                ORMGroup.group_type.in_(
                    (GroupType.PUBLIC, GroupType.PRIVATE)
                ),
                ORMGroup.deleted_at.is_(None),
                ORMUser.status == ActivityStatus.ACTIVE,
                ORMUser.deleted_at.is_(None),
            )
            .limit(1)
        )

        return await self._session.scalar(statement) is not None

    async def list_online_group_members(
        self,
        *,
        group_id: str,
        online_user_ids: set[str],
    ) -> list[OnlineGroupMember]:
        """Return online group members without exposing email addresses."""

        if not online_user_ids:
            return []

        parsed_ids: list[UUID] = []
        for user_id in online_user_ids:
            try:
                parsed_ids.append(UUID(user_id))
            except (TypeError, ValueError):
                # Redis presence is temporary and untrusted storage.
                continue

        if not parsed_ids:
            return []

        statement = (
            select(
                ORMUser.user_id,
                ORMUser.fullname,
                ORMMembership.member_role,
            )
            .join(
                ORMMembership,
                ORMMembership.user_id == ORMUser.user_id,
            )
            .join(
                ORMGroup,
                ORMGroup.group_id == ORMMembership.group_id,
            )
            .where(
                ORMMembership.group_id == self._uuid(group_id),
                ORMUser.user_id.in_(parsed_ids),
                ORMUser.show_online_status.is_(True),
                ORMUser.status == ActivityStatus.ACTIVE,
                ORMUser.deleted_at.is_(None),
                ORMGroup.group_type.in_(
                    (GroupType.PUBLIC, GroupType.PRIVATE)
                ),
                ORMGroup.deleted_at.is_(None),
            )
            .order_by(
                (ORMMembership.member_role == "owner").desc(),
                (ORMMembership.member_role == "admin").desc(),
                ORMUser.fullname,
            )
        )

        rows = await self._session.execute(statement)

        return [
            OnlineGroupMember(
                user_id=str(row.user_id),
                full_name=row.fullname,
                role=StudyGroupMemberRole(row.member_role.value),
            )
            for row in rows
        ]