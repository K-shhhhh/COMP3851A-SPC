# Public notifications request/response shapes used by FastAPI validation and OpenAPI.
# Coordinate field-name changes with the frontend; schemas alone do not enforce permissions.
from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    recipient_id: int
    is_read: bool


class CreateNotificationRequest(BaseModel):
    title: str
    message: str
    recipient_id: int
