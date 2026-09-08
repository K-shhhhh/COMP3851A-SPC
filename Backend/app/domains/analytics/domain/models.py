# Analytics domain data objects, independent of FastAPI and database libraries.
# These dataclasses are not database tables or migrations.
from dataclasses import dataclass


@dataclass(slots=True)
class AnalyticsSummary:
    """Represents dashboard analytics."""

    total_users: int
    total_notes: int
    total_study_groups: int
    total_notifications: int
