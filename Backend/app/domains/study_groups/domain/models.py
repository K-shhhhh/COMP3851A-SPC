"""Framework-independent domain models for collaborative study groups.

This module contains business objects only. It must not import FastAPI,
Pydantic, SQLAlchemy, or PostgreSQL-specific classes.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.domains.chats.domain.models import ChatSource


class StudyGroupVisibility(StrEnum):
    """Visibility options supported by collaborative study groups."""

    PUBLIC = "public"
    PRIVATE = "private"


class StudyGroupMemberRole(StrEnum):
    """Permissions assigned through an active group membership."""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class MyGroupsFilter(StrEnum):
    """Filters supported by the My Groups endpoint."""

    ALL = "all"
    PUBLIC = "public"
    PRIVATE = "private"
    OWNED = "owned"


class StudyGroupAiMode(StrEnum):
    """Explicit companion modes selectable from the group-chat @ menu."""

    DEFAULT = "default"
    SUMMARIZER = "summarizer"
    QUIZ = "quiz"
    FACILITATOR = "facilitator"


@dataclass(frozen=True, slots=True)
class StudyGroup:
    """One persisted public or private study group.

    Personal AI groups belong to the personal-chat module and must not be
    returned through Study Group endpoints.
    """

    group_id: str
    name: str
    visibility: StudyGroupVisibility
    description: str | None
    created_by: str
    current_admin_id: str
    max_members: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        """Enforce invariants shared by every persistence adapter."""

        if not self.group_id.strip():
            raise ValueError("group_id must not be empty")
        if not self.name.strip():
            raise ValueError("group name must not be empty")
        if len(self.name) > 100:
            raise ValueError("group name must not exceed 100 characters")
        if not self.created_by.strip():
            raise ValueError("created_by must not be empty")
        if not self.current_admin_id.strip():
            raise ValueError("current_admin_id must not be empty")
        if self.max_members <= 0:
            raise ValueError("max_members must be greater than zero")


@dataclass(frozen=True, slots=True)
class StudyGroupSummary:
    """Group information enriched for the authenticated student.

    The repository calculates membership fields for the authenticated user.
    The frontend may use them for presentation, but backend authorization does
    not trust values supplied by the frontend.
    """

    group: StudyGroup
    member_count: int
    is_member: bool
    is_owner: bool
    membership_role: StudyGroupMemberRole | None = None

    def __post_init__(self) -> None:
        """Validate membership-related projection values."""

        if self.member_count < 0:
            raise ValueError("member_count must not be negative")
        if self.is_member and self.membership_role is None:
            raise ValueError("an active member must have a membership role")
        if not self.is_member and self.membership_role is not None:
            raise ValueError("a nonmember cannot have a membership role")


@dataclass(frozen=True, slots=True)
class StudyGroupMembership:
    """One active relationship between a student and a study group."""

    membership_id: int
    group_id: str
    user_id: str
    role: StudyGroupMemberRole
    joined_at: datetime

    def __post_init__(self) -> None:
        """Validate membership identifiers."""

        if self.membership_id <= 0:
            raise ValueError("membership_id must be greater than zero")
        if not self.group_id.strip():
            raise ValueError("group_id must not be empty")
        if not self.user_id.strip():
            raise ValueError("user_id must not be empty")


@dataclass(frozen=True, slots=True)
class StudyGroupMember:
    """One group member enriched with safe public profile information.

    This projection combines membership data with the student's public profile
    so the frontend can display the group member list without exposing password
    hashes, account status internals, or other private database fields.
    """

    membership_id: int
    group_id: str
    user_id: str
    full_name: str
    email: str
    role: StudyGroupMemberRole
    joined_at: datetime

    def __post_init__(self) -> None:
        """Validate member projection values."""

        if self.membership_id <= 0:
            raise ValueError(
                "membership_id must be greater than zero"
            )

        if not self.group_id.strip():
            raise ValueError("group_id must not be empty")

        if not self.user_id.strip():
            raise ValueError("user_id must not be empty")

        if not self.full_name.strip():
            raise ValueError("full_name must not be empty")

        if not self.email.strip():
            raise ValueError("email must not be empty")


@dataclass(frozen=True, slots=True)
class StudyGroupChannel:
    """One named conversation channel inside a public or private group."""

    channel_id: str
    group_id: str
    name: str
    description: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        """Enforce channel invariants independently of persistence."""

        if not self.channel_id.strip():
            raise ValueError("channel_id must not be empty")
        if not self.group_id.strip():
            raise ValueError("group_id must not be empty")
        if not self.name.strip():
            raise ValueError("channel name must not be empty")
        if len(self.name) > 100:
            raise ValueError("channel name must not exceed 100 characters")
        if not self.created_by.strip():
            raise ValueError("created_by must not be empty")


@dataclass(frozen=True, slots=True)
class StudyGroupAiResponse:
    """One persisted companion response linked to a student message."""

    response_id: int
    mode: StudyGroupAiMode
    content: str
    generated_at: datetime
    sources: tuple[ChatSource, ...] = ()

    def __post_init__(self) -> None:
        """Validate provider-neutral companion response data."""

        if self.response_id <= 0:
            raise ValueError("response_id must be greater than zero")
        if not self.content.strip():
            raise ValueError("AI response content must not be empty")


@dataclass(frozen=True, slots=True)
class StudyGroupMessage:
    """One student-authored message inside a Study Group channel.

    The model contains no FastAPI, Pydantic, SQLAlchemy, PostgreSQL, or
    WebSocket behavior. It represents the business data shared by every
    persistence implementation.

    `group_id` is included even though the database message row references a
    channel. Keeping both identifiers in the domain model makes the
    authorization boundary explicit and helps prevent cross-group access.
    """

    message_id: int
    group_id: str
    channel_id: str
    author_id: str
    content: str
    sent_at: datetime
    mentioned_user_ids: tuple[str, ...] = ()
    ai_mode_used: StudyGroupAiMode | None = None
    ai_response: StudyGroupAiResponse | None = None
    edited_at: datetime | None = None
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        """Validate message invariants shared by every adapter."""

        if self.message_id <= 0:
            raise ValueError(
                "message_id must be greater than zero"
            )

        if not self.group_id.strip():
            raise ValueError(
                "group_id must not be empty"
            )

        if not self.channel_id.strip():
            raise ValueError(
                "channel_id must not be empty"
            )

        if not self.author_id.strip():
            raise ValueError(
                "author_id must not be empty"
            )

        if not self.content.strip():
            raise ValueError(
                "message content must not be empty"
            )

        if len(self.content) > 4000:
            raise ValueError(
                "message content must not exceed 4000 characters"
            )

        if len(self.mentioned_user_ids) > 20:
            raise ValueError(
                "a message must not mention more than 20 users"
            )

        if len(set(self.mentioned_user_ids)) != len(
            self.mentioned_user_ids
        ):
            raise ValueError(
                "mentioned_user_ids must not contain duplicates"
            )

        if any(not user_id.strip() for user_id in self.mentioned_user_ids):
            raise ValueError(
                "mentioned user identifiers must not be empty"
            )

        if self.ai_response is not None:
            if self.ai_mode_used is None:
                raise ValueError(
                    "an AI response requires an AI mode"
                )
            if self.ai_response.mode != self.ai_mode_used:
                raise ValueError(
                    "AI response mode must match the message AI mode"
                )
