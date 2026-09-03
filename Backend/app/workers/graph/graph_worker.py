# Graph worker placeholder: process() has no implementation and is not a registered Celery task.
# Implement long-running work here after agreeing on input, result and retry contracts.
# Owner: Krish implements this application/background/AI behavior.
class GraphWorker:
    """Builds the knowledge graph."""

    async def process(
        self,
        payload: dict,
    ):
        pass
