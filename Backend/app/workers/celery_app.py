# Celery entry point used by the worker container; Redis is the broker/result backend.
# Only the health task is registered here; business worker classes are not active tasks.
# Owner: Krish implements Celery tasks and Redis-backed job behavior.
import os

from celery import Celery


celery_app = Celery(
    "spc",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1"),
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
