"""PostgreSQL persistence for student quiz attempts."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.learning_progress.domain.models import QuizAttempt
from app.domains.learning_progress.domain.repository import (
    LearningProgressRepository,
)
from app.models.orm_models import QuizAttempt as ORMQuizAttempt


class PostgreSQLLearningProgressRepository(LearningProgressRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _parse_uuid(value: str) -> uuid.UUID:
        try:
            return uuid.UUID(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("student_user_id must be a valid UUID") from exc

    @staticmethod
    def _to_domain(row: ORMQuizAttempt) -> QuizAttempt:
        return QuizAttempt(
            attempt_id=row.attempt_id,
            student_user_id=str(row.student_user_id),
            topic=row.topic,
            is_correct=row.is_correct,
            attempted_at=row.attempted_at,
        )

    async def record_attempt(
        self,
        *,
        student_user_id: str,
        topic: str,
        is_correct: bool,
    ) -> QuizAttempt:
        row = ORMQuizAttempt(
            student_user_id=self._parse_uuid(student_user_id),
            topic=topic,
            is_correct=is_correct,
            attempted_at=datetime.now(timezone.utc),
        )
        self.session.add(row)

        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(row)
        return self._to_domain(row)

    async def list_attempts(
        self,
        *,
        student_user_id: str,
    ) -> list[QuizAttempt]:
        student_uuid = self._parse_uuid(student_user_id)

        result = await self.session.scalars(
            select(ORMQuizAttempt)
            .where(ORMQuizAttempt.student_user_id == student_uuid)
            .order_by(
                ORMQuizAttempt.attempted_at.asc(),
                ORMQuizAttempt.attempt_id.asc(),
            )
        )

        return [self._to_domain(row) for row in result.all()]
