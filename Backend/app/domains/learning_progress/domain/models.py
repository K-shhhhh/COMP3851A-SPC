"""Private student learning-progress domain models."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class TopicMastery(StrEnum):
    NEEDS_REVIEW = "needs_review"
    DEVELOPING = "developing"
    GOOD = "good"
    STRONG = "strong"


@dataclass(frozen=True, slots=True)
class QuizAttempt:
    attempt_id: int
    student_user_id: str
    topic: str
    is_correct: bool
    attempted_at: datetime


@dataclass(frozen=True, slots=True)
class TopicProgress:
    topic: str
    attempts: int
    correct: int
    accuracy_percent: int
    status: TopicMastery


@dataclass(frozen=True, slots=True)
class LearningProgress:
    total_attempts: int
    topics: tuple[TopicProgress, ...]
    review_next: tuple[TopicProgress, ...]
