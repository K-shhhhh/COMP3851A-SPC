# Administration domain data objects, independent of FastAPI and database libraries.
# These dataclasses are not database tables or migrations.
from dataclasses import dataclass


@dataclass(slots=True)
class SystemStatus:
    """Represents the overall system status."""

    application_name: str
    version: str
    environment: str
    database_status: str
    ai_service_status: str
