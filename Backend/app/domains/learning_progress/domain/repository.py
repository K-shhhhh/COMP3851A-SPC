"""Persistence contract for private student quiz history."""

from abc import ABC, abstractmethod

from app.domains.learning_progress.domain.models import QuizAttempt


class LearningProgressRepository(ABC):
    @abstractmethod
    async def record_attempt(
        self,
        *,
        student_user_id: str,
        topic: str,
        is_correct: bool,
    ) -> QuizAttempt:
        """Persist one quiz result for the authenticated student."""
        raise NotImplementedError

    @abstractmethod
    async def list_attempts(
        self,
        *,
        student_user_id: str,
    ) -> list[QuizAttempt]:
        """Return only quiz attempts belonging to one authenticated student."""
        raise NotImplementedError
