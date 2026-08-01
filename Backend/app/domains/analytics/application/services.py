from app.domains.analytics.domain.repository import (
    AnalyticsRepository,
)


class AnalyticsService:

    def __init__(
        self,
        repository: AnalyticsRepository,
    ):
        self.repository = repository

    async def get_dashboard_summary(
        self,
    ):

        return await self.repository.get_dashboard_summary()