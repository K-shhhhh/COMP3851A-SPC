# Celery entry point used by the worker container; Redis is the broker/result backend.
# Only the health task is registered here; business worker classes are not active tasks.
# Owner: Krish implements Celery tasks and Redis-backed job behavior.
import os

from celery import Celery


celery_app = Celery(
    "spc",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1"),
    # Tells the worker process which modules to import at startup, so any
    # @celery_app.task defined there actually gets registered. Without this,
    # the file can exist and be perfectly correct, but the worker never
    # knows the task exists, and .delay() calls just queue forever unread.
    include=["app.workers.attachment.processing_worker"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)


@celery_app.task(name="spc.health")
def health() -> dict[str, str]:
    """Minimal task used to confirm that Redis and the worker are connected."""

    return {"status": "healthy", "service": "SPC Worker"}
