"""HTTP schemas for private student learning progress."""

from pydantic import BaseModel, ConfigDict

from app.domains.learning_progress.domain.models import TopicMastery


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
