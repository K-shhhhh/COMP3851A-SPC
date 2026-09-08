# DEMO administration repository: returns constructed objects instead of executing SQL.
# Do not interpret successful responses as persisted data or authenticated access.
from app.domains.administration.domain.models import (
    SystemStatus,
)
from app.domains.administration.domain.repository import (
    AdministrationRepository,
)


class PostgreSQLAdministrationRepository(
    AdministrationRepository
):

    async def get_system_status(
        self,
    ) -> SystemStatus:

        return SystemStatus(
            application_name="Smart Peer Companion",
            version="1.0.0",
            environment="Development",
            database_status="Connected",
            ai_service_status="Available",
        )
