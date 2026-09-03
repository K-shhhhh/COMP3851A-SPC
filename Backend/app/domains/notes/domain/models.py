# Notes domain data objects, independent of FastAPI and database libraries.
# These dataclasses are not database tables or migrations.
from dataclasses import dataclass


@dataclass(slots=True)
class Note:
    """Domain entity representing a study note."""

    id: int
    title: str
    content: str
    owner_id: int
