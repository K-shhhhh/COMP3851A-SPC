from app.domains.analytics.domain.models import (
    AnalyticsSummary,
)
from app.domains.analytics.domain.repository import (
    AnalyticsRepository,
)


class PostgreSQLAnalyticsRepository(
    AnalyticsRepository
):

    async def get_dashboard_summary(
        self,
    ) -> AnalyticsSummary:

        return AnalyticsSummary(
            total_users=25,
            total_notes=120,
            total_study_groups=8,
            total_notifications=42,
        )