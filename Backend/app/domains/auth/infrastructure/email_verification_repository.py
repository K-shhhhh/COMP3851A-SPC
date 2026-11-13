"""PostgreSQL persistence for one-time email verification challenges."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.domain.email_verification import EmailVerificationRepository
from app.domains.auth.domain.models import EmailVerificationChallenge
from app.models.orm_models import (
    EmailVerificationChallenge as ORMEmailVerificationChallenge,
    User as ORMUser,
)


class PostgreSQLEmailVerificationRepository(EmailVerificationRepository):
    """Store only code digests and verify the user in one transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_domain(
        challenge: ORMEmailVerificationChallenge,
        email: str,
    ) -> EmailVerificationChallenge:
        return EmailVerificationChallenge(
            id=str(challenge.challenge_id),
            user_id=str(challenge.user_id),
            email=email,
            code_hash=challenge.code_hash,
            expires_at=challenge.expires_at,
            attempt_count=challenge.attempt_count,
            created_at=challenge.created_at,
            consumed_at=challenge.consumed_at,
        )

    async def replace_challenge(
        self,
        *,
        user_id: str,
        email: str,
        code_hash: str,
        expires_at: datetime,
    ) -> EmailVerificationChallenge:
        user_uuid = uuid.UUID(user_id)
        now = datetime.now(timezone.utc)
        await self._session.execute(
            delete(ORMEmailVerificationChallenge).where(
                ORMEmailVerificationChallenge.user_id == user_uuid
            )
        )
        challenge = ORMEmailVerificationChallenge(
            challenge_id=uuid.uuid4(),
            user_id=user_uuid,
            code_hash=code_hash,
            expires_at=expires_at,
            attempt_count=0,
            created_at=now,
        )
        self._session.add(challenge)
        await self._session.commit()
        return self._to_domain(challenge, email)

    async def get_challenge_by_email(
        self,
        email: str,
    ) -> EmailVerificationChallenge | None:
        row = (
            await self._session.execute(
                select(ORMEmailVerificationChallenge, ORMUser.email)
                .join(ORMUser, ORMUser.user_id == ORMEmailVerificationChallenge.user_id)
                .where(func.lower(ORMUser.email) == email.casefold())
            )
        ).one_or_none()
        if row is None:
            return None
        return self._to_domain(row[0], row[1])

    async def record_failed_attempt(self, challenge_id: str) -> int:
        challenge_uuid = uuid.UUID(challenge_id)
        result = await self._session.execute(
            update(ORMEmailVerificationChallenge)
            .where(
                ORMEmailVerificationChallenge.challenge_id == challenge_uuid,
                ORMEmailVerificationChallenge.consumed_at.is_(None),
            )
            .values(attempt_count=ORMEmailVerificationChallenge.attempt_count + 1)
            .returning(ORMEmailVerificationChallenge.attempt_count)
        )
        attempts = result.scalar_one_or_none()
        await self._session.commit()
        return int(attempts or 0)

    async def consume_and_verify(
        self,
        *,
        challenge_id: str,
        verified_at: datetime,
    ) -> bool:
        challenge_uuid = uuid.UUID(challenge_id)
        try:
            challenge = await self._session.scalar(
                select(ORMEmailVerificationChallenge)
                .where(
                    ORMEmailVerificationChallenge.challenge_id == challenge_uuid,
                    ORMEmailVerificationChallenge.consumed_at.is_(None),
                )
                .with_for_update()
            )
            if challenge is None:
                await self._session.rollback()
                return False
            user = await self._session.scalar(
                select(ORMUser)
                .where(ORMUser.user_id == challenge.user_id)
                .with_for_update()
            )
            if user is None:
                await self._session.rollback()
                return False
            challenge.consumed_at = verified_at
            user.email_verified_at = verified_at
            user.last_updated_at = verified_at
            await self._session.commit()
            return True
        except Exception:
            await self._session.rollback()
            raise
