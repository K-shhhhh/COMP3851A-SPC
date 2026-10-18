"""Framework-independent models for account-wide online presence."""

from dataclasses import dataclass

from app.domains.study_groups.domain.models import StudyGroupMemberRole


@dataclass(frozen=True, slots=True)
class OnlineGroupMember:
    """Safe profile information for an online Study Group member."""

    user_id: str
    full_name: str
    role: StudyGroupMemberRole

    def __post_init__(self) -> None:
        """Reject incomplete online-member projections."""

        if not self.user_id.strip():
            raise ValueError("user_id must not be empty")

        if not self.full_name.strip():
            raise ValueError("full_name must not be empty")
