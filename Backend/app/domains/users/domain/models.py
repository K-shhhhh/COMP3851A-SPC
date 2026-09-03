# Users domain data objects, independent of FastAPI and database libraries.
# These dataclasses are not database tables or migrations.
from dataclasses import dataclass


@dataclass(slots=True)
class User:
    """Domain entity representing a system user."""

    id: int
    full_name: str
    email: str
    role: str
