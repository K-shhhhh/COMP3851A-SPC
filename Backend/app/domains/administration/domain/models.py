from dataclasses import dataclass


@dataclass(slots=True)
class SystemStatus:
    """Represents the overall system status."""

    application_name: str
    version: str
    environment: str
    database_status: str
    ai_service_status: str