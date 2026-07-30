from abc import ABC, abstractmethod

from app.domains.analytics.domain.models import AnalyticsSummary


class AnalyticsRepository(ABC):

    @abstractmethod
    async def get_dashboard_summary(
        self,
    ) -> AnalyticsSummary:
        raise NotImplementedError