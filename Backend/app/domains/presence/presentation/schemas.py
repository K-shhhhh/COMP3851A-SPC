"""Public request and response schemas for online presence."""

from pydantic import BaseModel

from app.domains.study_groups.domain.models import StudyGroupMemberRole


class PresencePreferenceResponse(BaseModel):
    """Current user's online-visibility preference."""

    show_online_status: bool


class UpdatePresencePreferenceRequest(BaseModel):
    """Replacement value for the online-visibility preference."""

    show_online_status: bool


class PresenceHeartbeatResponse(BaseModel):
    """Result of an authenticated presence heartbeat."""

    visible_online: bool


class OnlineMemberResponse(BaseModel):
    """Safe group-member information for the online list."""

    user_id: str
    full_name: str
    role: StudyGroupMemberRole


class OnlineMemberListResponse(BaseModel):
    """Online members visible to the requesting group member."""

    online_count: int
    items: list[OnlineMemberResponse]