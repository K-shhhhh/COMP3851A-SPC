# Public analytics request/response shapes used by FastAPI validation and OpenAPI.
# Coordinate field-name changes with the frontend; schemas alone do not enforce permissions.
from pydantic import BaseModel


class AnalyticsSummaryResponse(BaseModel):
    total_users: int
    total_notes: int
    total_study_groups: int
    total_notifications: int
