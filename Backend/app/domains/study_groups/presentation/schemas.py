"""API request and response schemas for Study Groups.

These Pydantic models validate HTTP data and map domain models into safe public
responses. They do not perform authorization or database operations.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.domains.study_groups.domain.models import (
    StudyGroupMemberRole,
    StudyGroupMembership,
    StudyGroupSummary,
    StudyGroupVisibility,
)


class CreateStudyGroupRequest(BaseModel):
    """Information supplied when creating a public or private group."""

    name: str = Field(
        min_length=1,
        max_length=100,
        examples=["COMP3851 Revision Group"],
    )
    description: str | None = Field(
        default=None,
        max_length=1000,
        examples=["Weekly revision sessions and shared notes."],
    )
    visibility: StudyGroupVisibility
    max_members: int = Field(
        gt=0,
        examples=[30],
    )


class UpdateStudyGroupRequest(BaseModel):
    """Complete replacement of editable group information.

    Because all fields are required, this schema is intended for a PUT
    endpoint. A later PATCH schema can make fields optional if needed.
    """

    name: str = Field(
        min_length=1,
        max_length=100,
    )
    description: str | None = Field(
        default=None,
        max_length=1000,
    )
    visibility: StudyGroupVisibility
    max_members: int = Field(gt=0)


class StudyGroupResponse(BaseModel):
    """Public group information enriched for the current student."""

    id: str
    name: str
    description: str | None
    visibility: StudyGroupVisibility

    created_by: str
    current_admin_id: str

    max_members: int
    member_count: int

    is_member: bool
    is_owner: bool
    can_manage: bool

    membership_role: StudyGroupMemberRole | None

    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_summary(
        cls,
        summary: StudyGroupSummary,
    ) -> "StudyGroupResponse":
        """Map an internal user-scoped group projection to JSON."""

        group = summary.group

        can_manage = (
            summary.is_owner
            or summary.membership_role == StudyGroupMemberRole.ADMIN
        )

        return cls(
            id=group.group_id,
            name=group.name,
            description=group.description,
            visibility=group.visibility,
            created_by=group.created_by,
            current_admin_id=group.current_admin_id,
            max_members=group.max_members,
            member_count=summary.member_count,
            is_member=summary.is_member,
            is_owner=summary.is_owner,
            can_manage=can_manage,
            membership_role=summary.membership_role,
            created_at=group.created_at,
            updated_at=group.updated_at,
        )


class StudyGroupListResponse(BaseModel):
    """Paginated Study Group collection."""

    items: list[StudyGroupResponse]
    page: int
    page_size: int
    total: int


class DiscoverPublicResponse(StudyGroupListResponse):
    """Response for the Discover Public page."""


class MyGroupsResponse(StudyGroupListResponse):
    """Response for the authenticated student's My Groups page."""


class StudyGroupMembershipResponse(BaseModel):
    """Public representation of one active membership."""

    id: int
    group_id: str
    user_id: str
    role: StudyGroupMemberRole
    joined_at: datetime

    @classmethod
    def from_membership(
        cls,
        membership: StudyGroupMembership,
    ) -> "StudyGroupMembershipResponse":
        """Map a domain membership into an API response."""

        return cls(
            id=membership.membership_id,
            group_id=membership.group_id,
            user_id=membership.user_id,
            role=membership.role,
            joined_at=membership.joined_at,
        )