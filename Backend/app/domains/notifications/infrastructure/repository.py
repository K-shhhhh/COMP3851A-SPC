"""PostgreSQL persistence for notification preferences and notification inboxes."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.domains.notifications.domain.models import (
    Notification as DomainNotification,
    NotificationPreferences,
    NotificationType as DomainNotificationType,
)
from app.domains.notifications.domain.repository import (
    NotificationPreferenceRepository,
    NotificationRepository,
)
from app.models.orm_models import (
    ActivityStatus,
    Channel as ORMChannel,
    Group as ORMGroup,
    InAppNotificationType,
    Membership as ORMMembership,
    Message as ORMMessage,
    Notification as ORMNotification,
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


class PostgreSQLNotificationRepository(NotificationRepository):
    """Store and query an authenticated user's in-app notification inbox."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _parse_uuid(user_id: str) -> uuid.UUID | None:
        try:
            return uuid.UUID(user_id)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _preview(content: str) -> str:
        normalized = " ".join(content.split())
        return normalized[:160]

    def _visible_query(self, user_id: uuid.UUID):
        actor = aliased(ORMUser)
        statement = (
            select(
                ORMNotification,
                actor.fullname.label("actor_full_name"),
                ORMGroup.group_name,
                ORMChannel.channel_name,
                ORMMessage.message_content,
            )
            .join(actor, actor.user_id == ORMNotification.actor_user_id)
            .join(ORMMessage, ORMMessage.message_id == ORMNotification.message_id)
            .join(ORMChannel, ORMChannel.channel_id == ORMNotification.channel_id)
            .join(ORMGroup, ORMGroup.group_id == ORMNotification.group_id)
            .join(
                ORMMembership,
                and_(
                    ORMMembership.group_id == ORMNotification.group_id,
                    ORMMembership.user_id == ORMNotification.recipient_user_id,
                ),
            )
            .where(
                ORMNotification.recipient_user_id == user_id,
                ORMMessage.deleted_at.is_(None),
                ORMChannel.deleted_at.is_(None),
                ORMGroup.deleted_at.is_(None),
                actor.deleted_at.is_(None),
            )
        )
        return statement

    def _to_domain(self, row) -> DomainNotification:
        notification = row[0]
        return DomainNotification(
            notification_id=notification.notification_id,
            notification_type=DomainNotificationType(
                notification.notification_type.value
            ),
            actor_user_id=str(notification.actor_user_id),
            actor_full_name=row.actor_full_name,
            group_id=str(notification.group_id),
            group_name=row.group_name,
            channel_id=str(notification.channel_id),
            channel_name=row.channel_name,
            message_id=notification.message_id,
            message_preview=self._preview(row.message_content),
            created_at=notification.created_at,
            read_at=notification.read_at,
        )

    async def list_notifications(
        self,
        *,
        user_id: str,
        before_id: int | None,
        limit: int,
        unread_only: bool,
    ) -> tuple[list[DomainNotification], bool]:
        parsed_user_id = self._parse_uuid(user_id)
        if parsed_user_id is None:
            return [], False
        statement = self._visible_query(parsed_user_id)
        if before_id is not None:
            statement = statement.where(
                ORMNotification.notification_id < before_id
            )
        if unread_only:
            statement = statement.where(ORMNotification.read_at.is_(None))
        rows = (
            await self.session.execute(
                statement.order_by(ORMNotification.notification_id.desc())
                .limit(limit + 1)
            )
        ).all()
        return [self._to_domain(row) for row in rows[:limit]], len(rows) > limit

    async def count_unread(self, *, user_id: str) -> int:
        parsed_user_id = self._parse_uuid(user_id)
        if parsed_user_id is None:
            return 0
        visible = self._visible_query(parsed_user_id).where(
            ORMNotification.read_at.is_(None)
        )
        return int(
            await self.session.scalar(
                select(func.count()).select_from(visible.subquery())
            )
            or 0
        )

    async def mark_read(
        self,
        *,
        user_id: str,
        notification_id: int,
    ) -> DomainNotification | None:
        parsed_user_id = self._parse_uuid(user_id)
        if parsed_user_id is None:
            return None
        try:
            row = (
                await self.session.execute(
                    self._visible_query(parsed_user_id).where(
                        ORMNotification.notification_id == notification_id
                    )
                )
            ).first()
            if row is None:
                return None
            notification = row[0]
            if notification.read_at is None:
                notification.read_at = datetime.now(timezone.utc)
                await self.session.commit()
            return self._to_domain(row)
        except Exception:
            await self.session.rollback()
            raise

    async def mark_all_read(self, *, user_id: str) -> int:
        parsed_user_id = self._parse_uuid(user_id)
        if parsed_user_id is None:
            return 0
        try:
            result = await self.session.execute(
                update(ORMNotification)
                .where(
                    ORMNotification.recipient_user_id == parsed_user_id,
                    ORMNotification.read_at.is_(None),
                )
                .values(read_at=datetime.now(timezone.utc))
            )
            await self.session.commit()
            return int(result.rowcount or 0)
        except Exception:
            await self.session.rollback()
            raise


__all__ = (
    "PostgreSQLNotificationPreferenceRepository",
    "PostgreSQLNotificationRepository",
)
