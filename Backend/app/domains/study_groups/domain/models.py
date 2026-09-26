"""Framework-independent domain models for collaborative study groups.

This module contains business objects only. It must not import FastAPI,
Pydantic, SQLAlchemy, or PostgreSQL-specific classes.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class StudyGroupVisibility(StrEnum):
    """Visibility options supported by collaborative study groups."""

    PUBLIC = "public"
    PRIVATE = "private"


class StudyGroupMemberRole(StrEnum):
    """Permissions assigned through an active group membership."""

    ADMIN = "admin"
    MEMBER = "member"


class MyGroupsFilter(StrEnum):
    """Filters supported by the My Groups endpoint."""

    ALL = "all"
    PUBLIC = "public"
    PRIVATE = "private"
    OWNED = "owned"


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
