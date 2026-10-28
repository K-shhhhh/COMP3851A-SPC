"""Learning-progress use cases and topic mastery calculation."""

from collections import defaultdict

from app.domains.learning_progress.domain.models import (
    LearningProgress,
    QuizAttempt,
    TopicMastery,
    TopicProgress,
)
from app.domains.learning_progress.domain.repository import (
    LearningProgressRepository,
)


class LearningProgressService:
    def __init__(self, repository: LearningProgressRepository) -> None:
        self.repository = repository

    @staticmethod
    def _clean_topic(topic: str) -> str:
        cleaned = " ".join(topic.split())
        if not cleaned or len(cleaned) > 100:
            raise ValueError("Topic must contain between 1 and 100 characters.")
        return cleaned

    @staticmethod
    def _mastery(accuracy_percent: int) -> TopicMastery:
        if accuracy_percent < 50:
            return TopicMastery.NEEDS_REVIEW
        if accuracy_percent < 70:
            return TopicMastery.DEVELOPING
        if accuracy_percent < 85:
            return TopicMastery.GOOD
        return TopicMastery.STRONG

    async def record_quiz_result(
        self,
        *,
        student_user_id: str,
        topic: str,
        is_correct: bool,
    ) -> QuizAttempt:
        """Record a graded result from trusted backend quiz logic.

        This method is intentionally not exposed as a student HTTP endpoint.
        The authenticated dashboard is read-only so students cannot submit
        arbitrary correctness values and inflate their own progress.
        """

        return await self.repository.record_attempt(
            student_user_id=student_user_id,
            topic=self._clean_topic(topic),
            is_correct=is_correct,
        )

    async def get_learning_progress(
        self,
        *,
        student_user_id: str,
    ) -> LearningProgress:
        attempts = await self.repository.list_attempts(
            student_user_id=student_user_id,
        )

        aggregates: dict[str, dict[str, object]] = defaultdict(
            lambda: {"display": "", "attempts": 0, "correct": 0}
        )

        for attempt in attempts:
            display_topic = self._clean_topic(attempt.topic)
            key = display_topic.casefold()
            bucket = aggregates[key]

            if not bucket["display"]:
                bucket["display"] = display_topic

            bucket["attempts"] = int(bucket["attempts"]) + 1
            if attempt.is_correct:
                bucket["correct"] = int(bucket["correct"]) + 1

        topics: list[TopicProgress] = []

        for bucket in aggregates.values():
            attempt_count = int(bucket["attempts"])
            correct_count = int(bucket["correct"])
            accuracy = round((correct_count / attempt_count) * 100)

            topics.append(
                TopicProgress(
                    topic=str(bucket["display"]),
                    attempts=attempt_count,
                    correct=correct_count,
                    accuracy_percent=accuracy,
                    status=self._mastery(accuracy),
                )
            )

        topics.sort(key=lambda item: item.topic.casefold())

        review_next = sorted(
            topics,
            key=lambda item: (
                item.accuracy_percent,
                -item.attempts,
                item.topic.casefold(),
            ),
        )[:3]

        return LearningProgress(
            total_attempts=len(attempts),
            topics=tuple(topics),
            review_next=tuple(review_next),
        )
