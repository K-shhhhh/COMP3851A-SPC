# Administration use cases depend on repository interfaces, not HTTP or SQL.
# Current methods delegate to repositories; authorization and business rules still need implementation.
from app.domains.administration.domain.repository import (
    AdministrationRepository,
)


class AdministrationService:

    def __init__(
        self,
        repository: AdministrationRepository,
    ):
        self.repository = repository

    async def get_system_status(
        self,
    ):

        return await self.repository.get_system_status()
