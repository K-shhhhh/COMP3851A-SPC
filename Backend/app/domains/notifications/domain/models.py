# Notifications domain data objects, independent of FastAPI and database libraries.
# These dataclasses are not database tables or migrations.
from dataclasses import dataclass


@dataclass(slots=True)
class Notification:
    """Domain entity representing a notification."""

    id: int
    title: str
    message: str
    recipient_id: int
    is_read: bool
