"""Unit tests for Study Group application rules using local memory."""

import pytest

from app.domains.study_groups.application.services import StudyGroupService
from app.domains.study_groups.domain.exceptions import (
    PrivateStudyGroupJoinError,
    StudyGroupAlreadyMemberError,
    StudyGroupNotFoundError,
    StudyGroupPermissionDeniedError,
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

