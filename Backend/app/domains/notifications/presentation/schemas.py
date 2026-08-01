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