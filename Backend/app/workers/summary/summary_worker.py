# Summary worker placeholder: process() has no implementation and is not a registered Celery task.
# Implement long-running work here after agreeing on input, result and retry contracts.
class SummaryWorker:
    """Generates summaries."""

    async def process(
        self,
        payload: dict,
    ):
        pass
