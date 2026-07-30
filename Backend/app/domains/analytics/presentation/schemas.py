from pydantic import BaseModel


class AnalyticsSummaryResponse(BaseModel):
    total_users: int
    total_notes: int
    total_study_groups: int
    total_notifications: int