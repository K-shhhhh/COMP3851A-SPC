from pydantic import BaseModel


class SystemStatusResponse(BaseModel):
    application_name: str
    version: str
    environment: str
    database_status: str
    ai_service_status: str