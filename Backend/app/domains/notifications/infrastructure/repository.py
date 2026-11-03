"""PostgreSQL repository implementation for per-user notification preferences."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.notifications.domain.models import NotificationPreferences
from app.domains.notifications.domain.repository import (
    NotificationPreferenceRepository,
)
from app.models.orm_models import (
    ActivityStatus,
    NotificationPreference as ORMNotificationPreference,
    User as ORMUser,
)


class PostgreSQLNotificationPreferenceRepository(
    NotificationPreferenceRepository
):
    """Persist and read per-user notification preferences in PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _parse_uuid(user_id: str) -> uuid.UUID | None:
        try:
            return uuid.UUID(user_id)
        except (TypeError, ValueError):
            return None

    async def get_preferences(
        self,
        user_id: str,
    ) -> NotificationPreferences:
        """Return persisted values, using both ``True`` as creation defaults."""

        parsed_user_id = self._parse_uuid(user_id)
        if parsed_user_id is None:
            return NotificationPreferences(
                new_group_messages=True,
                group_mentions=True,
            )

        statement = (
            select(ORMNotificationPreference)
            .join(
                ORMUser,
                ORMUser.user_id == ORMNotificationPreference.user_id,
            )
            .where(
                ORMNotificationPreference.user_id == parsed_user_id,
                ORMUser.status == ActivityStatus.ACTIVE,
                ORMUser.deleted_at.is_(None),
            )
        )

        orm_pref = await self.session.scalar(statement)
        if orm_pref is None:
            return NotificationPreferences(
                new_group_messages=True,
                group_mentions=True,
            )

        return NotificationPreferences(
            new_group_messages=bool(orm_pref.new_group_messages),
            group_mentions=bool(orm_pref.group_mentions),
        )

    async def update_preferences(
        self,
        *,
        user_id: str,
        new_group_messages: bool | None,
        group_mentions: bool | None,
    ) -> NotificationPreferences:
        """Atomically apply supplied preference values and return the result."""

        parsed_user_id = self._parse_uuid(user_id)
        if parsed_user_id is None:
            raise ValueError("user_id must be a valid UUID.")

        user_statement = select(ORMUser).where(
            ORMUser.user_id == parsed_user_id,
            ORMUser.status == ActivityStatus.ACTIVE,
            ORMUser.deleted_at.is_(None),
        )
        orm_user = await self.session.scalar(user_statement)
        if orm_user is None:
            raise LookupError("Active user account was not found.")

        pref_statement = select(ORMNotificationPreference).where(
            ORMNotificationPreference.user_id == parsed_user_id,
        )
        orm_pref = await self.session.scalar(pref_statement)

        try:
            if orm_pref is None:
                orm_pref = ORMNotificationPreference(
                    user_id=parsed_user_id,
                    new_group_messages=(
                        True
                        if new_group_messages is None
                        else new_group_messages
                    ),
                    group_mentions=(
                        True if group_mentions is None else group_mentions
                    ),
                )
                self.session.add(orm_pref)
            else:
                if new_group_messages is not None:
                    orm_pref.new_group_messages = new_group_messages
                if group_mentions is not None:
                    orm_pref.group_mentions = group_mentions

            await self.session.commit()

        except Exception:
            await self.session.rollback()
            raise

        return NotificationPreferences(
            new_group_messages=bool(orm_pref.new_group_messages),
            group_mentions=bool(orm_pref.group_mentions),
        )
