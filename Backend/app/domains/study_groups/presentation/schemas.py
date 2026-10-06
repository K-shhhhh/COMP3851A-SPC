"""API request and response schemas for Study Groups.

These Pydantic models validate HTTP data and map domain models into safe public
responses. They do not perform authorization or database operations.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.domains.chats.domain.models import ChatSource
from app.domains.study_groups.domain.models import (
    StudyGroupAiMode,
    StudyGroupAiResponse,
    StudyGroupChannel,
    StudyGroupMessage,
    StudyGroupMemberRole,
    StudyGroupMember,
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


class AddStudyGroupMemberRequest(BaseModel):
    """Student account an owner/admin wants to add to a group."""

    email: EmailStr


class UpdateStudyGroupMemberRoleRequest(BaseModel):
    """Owner-selected role for an existing non-owner membership."""

    role: Literal["member", "admin"]


class TransferStudyGroupOwnershipRequest(BaseModel):
    """Existing active member who should become the new owner."""

    new_owner_user_id: UUID


class CreateStudyGroupChannelRequest(BaseModel):
    """Administrator-supplied information for a new channel."""

    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)


class UpdateStudyGroupChannelRequest(BaseModel):
    """Complete replacement of editable channel information."""

    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)


class CreateStudyGroupMessageRequest(BaseModel):
    """Text and structured human mentions supplied for a channel message."""

    content: str = Field(min_length=1, max_length=4000)
    mentioned_user_ids: list[UUID] = Field(
        default_factory=list,
        max_length=20,
    )
    ai_mode: StudyGroupAiMode | None = None
    response_format: Literal[
        "paragraph",
        "bullet_points",
        "table",
    ] | None = None


class UpdateStudyGroupMessageRequest(BaseModel):
    """Replacement text and mentions supplied when an author edits."""

    content: str = Field(min_length=1, max_length=4000)
    mentioned_user_ids: list[UUID] = Field(
        default_factory=list,
        max_length=20,
    )


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

        can_manage = summary.is_member and summary.membership_role in (
            StudyGroupMemberRole.OWNER, StudyGroupMemberRole.ADMIN,
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


class StudyGroupMemberResponse(BaseModel):
    """Safe public profile and membership information."""

    membership_id: int
    group_id: str
    user_id: str
    full_name: str
    email: EmailStr
    role: StudyGroupMemberRole
    joined_at: datetime

    @classmethod
    def from_member(
        cls,
        member: StudyGroupMember,
    ) -> "StudyGroupMemberResponse":
        """Map a member projection into the HTTP response."""

        return cls(
            membership_id=member.membership_id,
            group_id=member.group_id,
            user_id=member.user_id,
            full_name=member.full_name,
            email=member.email,
            role=member.role,
            joined_at=member.joined_at,
        )


class StudyGroupMemberListResponse(BaseModel):
    """Paginated member collection."""

    items: list[StudyGroupMemberResponse]
    page: int
    page_size: int
    total: int


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


class StudyGroupChannelResponse(BaseModel):
    """Public representation of one active study-group channel."""

    id: str
    group_id: str
    name: str
    description: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_channel(
        cls,
        channel: StudyGroupChannel,
    ) -> "StudyGroupChannelResponse":
        """Map a domain channel into the HTTP response."""

        return cls(
            id=channel.channel_id,
            group_id=channel.group_id,
            name=channel.name,
            description=channel.description,
            created_by=channel.created_by,
            created_at=channel.created_at,
            updated_at=channel.updated_at,
        )


class StudyGroupChannelListResponse(BaseModel):
    """Paginated active-channel collection."""

    items: list[StudyGroupChannelResponse]
    page: int
    page_size: int
    total: int


class StudyGroupMessageSourceResponse(BaseModel):
    """Citation for a companion answer grounded in a channel attachment."""

    note_id: int
    note_title: str
    chunk_id: int
    page: int | None

    @classmethod
    def from_source(
        cls,
        source: ChatSource,
    ) -> "StudyGroupMessageSourceResponse":
        """Map one authorized source into the public response shape."""

        return cls(
            note_id=source.note_id,
            note_title=source.note_title,
            chunk_id=source.chunk_id,
            page=source.page,
        )


class StudyGroupCompanionResponse(BaseModel):
    """Generated companion answer linked to one student message."""

    id: int
    mode: StudyGroupAiMode
    content: str
    sources: list[StudyGroupMessageSourceResponse]
    generated_at: datetime

    @classmethod
    def from_response(
        cls,
        response: StudyGroupAiResponse,
    ) -> "StudyGroupCompanionResponse":
        """Map a persisted companion response into the API contract."""

        return cls(
            id=response.response_id,
            mode=response.mode,
            content=response.content,
            sources=[
                StudyGroupMessageSourceResponse.from_source(source)
                for source in response.sources
            ],
            generated_at=response.generated_at,
        )


class StudyGroupMessageResponse(BaseModel):
    """Public representation of one active normal channel message."""

    id: int
    group_id: str
    channel_id: str
    author_id: str
    content: str
    mentioned_user_ids: list[str]
    ai_mode_used: StudyGroupAiMode | None
    ai_response: StudyGroupCompanionResponse | None
    sent_at: datetime
    edited_at: datetime | None

    @classmethod
    def from_message(
        cls,
        message: StudyGroupMessage,
    ) -> "StudyGroupMessageResponse":
        """Map a domain message into the HTTP response."""

        return cls(
            id=message.message_id,
            group_id=message.group_id,
            channel_id=message.channel_id,
            author_id=message.author_id,
            content=message.content,
            mentioned_user_ids=list(message.mentioned_user_ids),
            ai_mode_used=message.ai_mode_used,
            ai_response=(
                StudyGroupCompanionResponse.from_response(
                    message.ai_response
                )
                if message.ai_response is not None
                else None
            ),
            sent_at=message.sent_at,
            edited_at=message.edited_at,
        )


class StudyGroupMessageListResponse(BaseModel):
    """Paginated oldest-first collection of active channel messages."""

    items: list[StudyGroupMessageResponse]
    page: int
    page_size: int
    total: int
