# HTTP boundary for administration: parse request schemas and delegate through Depends.
# These scaffold routes still need authentication and resource-level authorization.
from fastapi import APIRouter, Depends

from app.api.dependencies import get_administration_service
from app.domains.administration.application.services import (
    AdministrationService,
)
from app.domains.administration.presentation.schemas import (
    SystemStatusResponse,
)

router = APIRouter(
    prefix="/administration",
    tags=["Administration"],
)


@router.get(
    "/system-status",
    response_model=SystemStatusResponse,
)
async def get_system_status(
    service: AdministrationService = Depends(
        get_administration_service,
    ),
):
    return await service.get_system_status()
