from fastapi import APIRouter, Depends

from app.api.dependencies import get_analytics_service
from app.domains.analytics.application.services import (
    AnalyticsService,
)
from app.domains.analytics.presentation.schemas import (
    AnalyticsSummaryResponse,
)

router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"],
)


@router.get(
    "/dashboard",
    response_model=AnalyticsSummaryResponse,
)
async def get_dashboard_summary(
    service: AnalyticsService = Depends(
        get_analytics_service,
    ),
):
    return await service.get_dashboard_summary()