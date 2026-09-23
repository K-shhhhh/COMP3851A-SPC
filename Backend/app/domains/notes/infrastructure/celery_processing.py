"""Real production-style dispatcher: hands attachment processing off to
Celery instead of running it inline during the upload request.

Replaces KrishAttachmentProcessingDispatcher (rag_processing.py) as the one
wired into dependencies.py. The actual processing logic now lives in
processing_worker.py, run by the worker container -- this class's only job
is to queue the task and return immediately.
"""

from app.domains.notes.domain.processing import AttachmentProcessingDispatcher
from app.workers.attachment.processing_worker import process_attachment_task


class CeleryAttachmentProcessingDispatcher(AttachmentProcessingDispatcher):
    """Queues processing on Celery instead of doing it inline."""

    async def dispatch(
        self,
        *,
        attachment_id: int,
        object_path: str,
    ) -> None:
        """Hand the task to Celery and return immediately.

        .delay() sends the task to Redis (the broker) and returns right
        away -- it does NOT wait for the worker to actually run it. That's
        the entire point: the upload request stays fast regardless of how
        long processing takes.
        """

        process_attachment_task.delay(attachment_id, object_path)
