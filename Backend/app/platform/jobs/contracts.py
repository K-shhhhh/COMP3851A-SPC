# Provider-neutral job state and queue interface, shared by application and worker code.
# This defines shapes only: it does not enqueue tasks or persist their state.
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol


class JobStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class JobRecord:
    job_id: str
    job_type: str
    status: JobStatus = JobStatus.QUEUED
    progress: int = 0
    message: str = "Job queued"
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class JobQueue(Protocol):
    async def enqueue(self, job_type: str, payload: dict[str, Any]) -> JobRecord:
        """Create a background job without exposing Celery to application code."""

    async def get(self, job_id: str) -> JobRecord | None:
        """Return the current job snapshot."""
