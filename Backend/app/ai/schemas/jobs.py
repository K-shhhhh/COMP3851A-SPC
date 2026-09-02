from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.platform.jobs.contracts import JobStatus


AIJobType = Literal["question", "summary", "quiz", "facilitator"]


class SubmitAIJobRequest(BaseModel):
    jobType: AIJobType
    inputText: str = Field(min_length=1, max_length=20_000)
    studyGroupId: str | None = None
    resourceIds: list[str] = Field(default_factory=list, max_length=50)
    options: dict[str, Any] = Field(default_factory=dict)


class JobError(BaseModel):
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] | None = None


class AIJobResponse(BaseModel):
    jobId: str
    jobType: AIJobType
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    message: str
    result: dict[str, Any] | None = None
    error: JobError | None = None
    createdAt: datetime
    updatedAt: datetime


class JobProgressEvent(AIJobResponse):
    event: Literal["job.progress", "job.completed", "job.failed"]
