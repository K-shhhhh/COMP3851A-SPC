"""HTTP schemas for private student learning progress."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domains.learning_progress.domain.models import TopicMastery


class QuizResultRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=100)
    is_correct: bool


class QuizResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    attempt_id: int
    topic: str
    is_correct: bool
    attempted_at: datetime


class TopicProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    topic: str
    attempts: int
    correct: int
    accuracy_percent: int
    status: TopicMastery


class LearningProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_attempts: int
    topics: list[TopicProgressResponse]
    review_next: list[TopicProgressResponse]
