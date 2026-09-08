# Public administration request/response shapes used by FastAPI validation and OpenAPI.
# Coordinate field-name changes with the frontend; schemas alone do not enforce permissions.
from pydantic import BaseModel


class SystemStatusResponse(BaseModel):
    application_name: str
    version: str
    environment: str
    database_status: str
    ai_service_status: str
