# Queue placeholder: returning True does not submit a Celery task.
# Implement the JobQueue contract and return a trackable job identifier.
class JobScheduler:
    """Background job scheduler."""

    async def enqueue(
        self,
        job_name: str,
        payload: dict,
    ):
        return True
