"""Unit tests for Study Group application rules using local memory."""

import pytest

from app.domains.study_groups.application.services import StudyGroupService
from app.domains.study_groups.domain.exceptions import (
    PrivateStudyGroupJoinError,
    StudyGroupAlreadyMemberError,
    StudyGroupChannelNameConflictError,
    StudyGroupChannelNotFoundError,
    StudyGroupNotFoundError,
    StudyGroupPermissionDeniedError,
    StudyGroupTargetUserNotFoundError,
)
from app.domains.study_groups.domain.models import (
    MyGroupsFilter,
    StudyGroupVisibility,
)
from app.domains.study_groups.infrastructure.memory_repository import (
    InMemoryStudyGroupRepository,
)


@pytest.fixture
def service() -> StudyGroupService:
    """Return an isolated Study Group service for each test."""

    return StudyGroupService(InMemoryStudyGroupRepository())


@pytest.mark.asyncio
async def test_discover_and_my_groups_have_distinct_visibility(service) -> None:
    """Discover exposes public groups while My Groups includes memberships."""

    owner = "11111111-1111-1111-1111-111111111111"
    visitor = "22222222-2222-2222-2222-222222222222"
    public_group = await service.create_group(
        user_id=owner,
        name="Public revision",
        description="Exam preparation",
        visibility=StudyGroupVisibility.PUBLIC,
        max_members=10,
    )
    await service.create_group(
        user_id=owner,
        name="Private revision",
        description=None,
        visibility=StudyGroupVisibility.PRIVATE,
        max_members=10,
    )

    discovered, total = await service.discover_public_groups(
        user_id=visitor,
        page=1,
        page_size=20,
        search="revision",
    )
    assert total == 1
    assert discovered[0].group.group_id == public_group.group.group_id
    assert discovered[0].is_member is False

    await service.join_public_group(
        group_id=public_group.group.group_id,
        user_id=visitor,
    )
    mine, mine_total = await service.list_my_groups(
        user_id=visitor,
        group_filter=MyGroupsFilter.ALL,
        page=1,
        page_size=20,
    )
    assert mine_total == 1
    assert mine[0].is_member is True


@pytest.mark.asyncio
async def test_join_leave_and_private_access_rules(service) -> None:
    """Enforce public joining, private isolation, and admin ownership."""

    owner = "11111111-1111-1111-1111-111111111111"
    member = "22222222-2222-2222-2222-222222222222"
    public_group = await service.create_group(
        user_id=owner,
        name="Public group",
        description=None,
        visibility=StudyGroupVisibility.PUBLIC,
        max_members=5,
    )
    private_group = await service.create_group(
        user_id=owner,
        name="Private group",
        description=None,
        visibility=StudyGroupVisibility.PRIVATE,
        max_members=5,
    )

    with pytest.raises(StudyGroupNotFoundError):
        await service.get_group(
            group_id=private_group.group.group_id,
            user_id=member,
        )
    with pytest.raises(PrivateStudyGroupJoinError):
        await service.join_public_group(
            group_id=private_group.group.group_id,
            user_id=member,
        )

    await service.join_public_group(
        group_id=public_group.group.group_id,
        user_id=member,
    )
    with pytest.raises(StudyGroupAlreadyMemberError):
        await service.join_public_group(
            group_id=public_group.group.group_id,
            user_id=member,
        )
    await service.leave_group(
        group_id=public_group.group.group_id,
        user_id=member,
    )

    with pytest.raises(StudyGroupPermissionDeniedError):
        await service.leave_group(
            group_id=public_group.group.group_id,
            user_id=owner,
        )


@pytest.mark.asyncio
async def test_non_admin_cannot_update_or_delete_group(service) -> None:
    """Keep group management restricted to owners and admins."""

    owner = "11111111-1111-1111-1111-111111111111"
    member = "22222222-2222-2222-2222-222222222222"
    group = await service.create_group(
        user_id=owner,
        name="Access control",
        description=None,
        visibility=StudyGroupVisibility.PUBLIC,
        max_members=5,
    )
    await service.join_public_group(
        group_id=group.group.group_id,
        user_id=member,
    )

    with pytest.raises(StudyGroupPermissionDeniedError):
        await service.update_group(
            group_id=group.group.group_id,
            user_id=member,
            name="Unauthorized rename",
            description=None,
            visibility=StudyGroupVisibility.PUBLIC,
            max_members=5,
        )


@pytest.mark.asyncio
async def test_admin_adds_lists_and_removes_member_by_email() -> None:
    """Cover the simplified private-group membership workflow."""

    repository = InMemoryStudyGroupRepository()
    service = StudyGroupService(repository)
    owner = "11111111-1111-1111-1111-111111111111"
    member = "22222222-2222-2222-2222-222222222222"
    await repository.seed_user(
        user_id=owner,
        full_name="Group Owner",
        email="owner@example.com",
    )
    await repository.seed_user(
        user_id=member,
        full_name="Group Member",
        email="member@example.com",
    )
    group = await service.create_group(
        user_id=owner,
        name="Private revision",
        description=None,
        visibility=StudyGroupVisibility.PRIVATE,
        max_members=5,
    )

    membership = await service.add_member_by_email(
        group_id=group.group.group_id,
        requester_user_id=owner,
        email="MEMBER@example.com",
    )
    assert membership.user_id == member

    members, total = await service.list_members(
        group_id=group.group.group_id,
        user_id=member,
        page=1,
        page_size=20,
    )
    assert total == 2
    assert [item.full_name for item in members] == [
        "Group Owner",
        "Group Member",
    ]

    await service.remove_member(
        group_id=group.group.group_id,
        requester_user_id=owner,
        target_user_id=member,
    )
    with pytest.raises(StudyGroupNotFoundError):
        await service.list_members(
            group_id=group.group.group_id,
            user_id=member,
            page=1,
            page_size=20,
        )


@pytest.mark.asyncio
async def test_admin_cannot_add_inactive_user_or_remove_owner() -> None:
    """Protect inactive accounts and administrative memberships."""

    repository = InMemoryStudyGroupRepository()
    service = StudyGroupService(repository)
    owner = "11111111-1111-1111-1111-111111111111"
    inactive = "33333333-3333-3333-3333-333333333333"
    await repository.seed_user(
        user_id=owner,
        full_name="Group Owner",
        email="owner@example.com",
    )
    await repository.seed_user(
        user_id=inactive,
        full_name="Inactive Student",
        email="inactive@example.com",
        is_active=False,
    )
    group = await service.create_group(
        user_id=owner,
        name="Protected group",
        description=None,
        visibility=StudyGroupVisibility.PRIVATE,
        max_members=5,
    )

    with pytest.raises(StudyGroupTargetUserNotFoundError):
        await service.add_member_by_email(
            group_id=group.group.group_id,
            requester_user_id=owner,
            email="inactive@example.com",
        )
    with pytest.raises(StudyGroupPermissionDeniedError):
        await service.remove_member(
            group_id=group.group.group_id,
            requester_user_id=owner,
            target_user_id=owner,
        )


@pytest.mark.asyncio
async def test_channel_lifecycle_and_member_permissions(service) -> None:
    """Allow members to read channels while only admins may manage them."""

    owner = "11111111-1111-1111-1111-111111111111"
    member = "22222222-2222-2222-2222-222222222222"
    group = await service.create_group(
        user_id=owner,
        name="Channel group",
        description=None,
        visibility=StudyGroupVisibility.PUBLIC,
        max_members=5,
    )
    group_id = group.group.group_id
    await service.join_public_group(group_id=group_id, user_id=member)

    created = await service.create_channel(
        group_id=group_id,
        user_id=owner,
        name="  Exam   preparation  ",
        description=" Week 8 revision ",
    )
    assert created.name == "Exam preparation"
    assert created.description == "Week 8 revision"

    channels, total = await service.list_channels(
        group_id=group_id,
        user_id=member,
        page=1,
        page_size=20,
    )
    assert total == 1
    assert channels[0].channel_id == created.channel_id

    with pytest.raises(StudyGroupPermissionDeniedError):
        await service.update_channel(
            group_id=group_id,
            channel_id=created.channel_id,
            user_id=member,
            name="Member rename",
            description=None,
        )

    with pytest.raises(StudyGroupChannelNameConflictError):
        await service.create_channel(
            group_id=group_id,
            user_id=owner,
            name="exam PREPARATION",
            description=None,
        )

    updated = await service.update_channel(
        group_id=group_id,
        channel_id=created.channel_id,
        user_id=owner,
        name="Final exam",
        description=None,
    )
    assert updated.name == "Final exam"

    await service.delete_channel(
        group_id=group_id,
        channel_id=created.channel_id,
        user_id=owner,
    )
    with pytest.raises(StudyGroupChannelNotFoundError):
        await service.get_channel(
            group_id=group_id,
            channel_id=created.channel_id,
            user_id=member,
        )


@pytest.mark.asyncio
async def test_nonmember_cannot_read_public_group_channels(service) -> None:
    """Require membership even when the containing group is public."""

    owner = "11111111-1111-1111-1111-111111111111"
    outsider = "33333333-3333-3333-3333-333333333333"
    group = await service.create_group(
        user_id=owner,
        name="Public channel group",
        description=None,
        visibility=StudyGroupVisibility.PUBLIC,
        max_members=5,
    )
    with pytest.raises(StudyGroupPermissionDeniedError):
        await service.list_channels(
            group_id=group.group.group_id,
            user_id=outsider,
            page=1,
            page_size=20,
        )
