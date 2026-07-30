from dataclasses import dataclass


@dataclass(slots=True)
class Notification:
    """Domain entity representing a notification."""

    id: int
    title: str
    message: str
    recipient_id: int
    is_read: bool