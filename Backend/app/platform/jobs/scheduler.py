class JobScheduler:
    """Background job scheduler."""

    async def enqueue(
        self,
        job_name: str,
        payload: dict,
    ):
        return True