"""Real PostgreSQL ownership constraints, rollback and concurrent transfers.

Uses the disposable-schema fixture and SPC_TEST_DATABASE_URL from the existing
persistence suite. No existing application tables are changed.
"""

import asyncio
from datetime import datetime, timezone
from uuid import UUID

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from tests.integration.test_study_group_persistence import sessions, add_user, add_group
from app.models.orm_models import Group, Membership, MemberRole
from app.domains.study_groups.domain.models import StudyGroupMemberRole
from app.domains.study_groups.domain.exceptions import StudyGroupPermissionDeniedError
from app.domains.study_groups.infrastructure.repository import PostgreSQLStudyGroupRepository


async def setup_members(sessions):
    async with sessions() as session:
        users = [await add_user(session, email=f'owner-test-{i}@example.com') for i in range(3)]
        group = await add_group(session, users[0])
        gid = group.group.group_id
        repo = PostgreSQLStudyGroupRepository(session)
        for user in users[1:]:
            await repo.create_membership(group_id=gid, user_id=str(user.user_id),
                role=StudyGroupMemberRole.MEMBER, joined_at=datetime.now(timezone.utc))
        return gid, [u.user_id for u in users]


@pytest.mark.asyncio
@pytest.mark.parametrize('failure_role', ['admin', 'owner'])
async def test_transfer_rolls_back_both_updates(sessions, failure_role):
    gid, users = await setup_members(sessions)
    async with sessions() as session:
        # A CHECK constraint injects a real SQL failure on demotion or promotion.
        target = users[0] if failure_role == 'admin' else users[1]
        await session.execute(text(f"ALTER TABLE memberships ADD CONSTRAINT reject_transfer "
            f"CHECK (user_id <> '{target}'::uuid OR member_role <> '{failure_role}')"))
        await session.commit()
        with pytest.raises(IntegrityError):
            await PostgreSQLStudyGroupRepository(session).transfer_ownership(
                group_id=gid, current_owner_id=str(users[0]), new_owner_id=str(users[1]))
    async with sessions() as session:
        repo = PostgreSQLStudyGroupRepository(session)
        assert (await repo.get_membership(group_id=gid, user_id=str(users[0]))).role == StudyGroupMemberRole.OWNER
        assert (await repo.get_membership(group_id=gid, user_id=str(users[1]))).role == StudyGroupMemberRole.MEMBER
        assert (await session.get(Group, UUID(gid))).current_owner == users[0]


@pytest.mark.asyncio
async def test_simultaneous_transfers_have_one_winner(sessions):
    gid, users = await setup_members(sessions)
    async def transfer(target):
        async with sessions() as session:
            return await PostgreSQLStudyGroupRepository(session).transfer_ownership(
                group_id=gid, current_owner_id=str(users[0]), new_owner_id=str(target))
    results = await asyncio.wait_for(
        asyncio.gather(transfer(users[1]), transfer(users[2]), return_exceptions=True), 15)
    assert sum(isinstance(result, tuple) for result in results) == 1
    assert sum(isinstance(result, StudyGroupPermissionDeniedError) for result in results) == 1
    async with sessions() as session:
        owners = (await session.scalars(select(Membership).where(
            Membership.group_id == UUID(gid), Membership.member_role == MemberRole.OWNER))).all()
        assert len(owners) == 1
        group = await session.get(Group, UUID(gid))
        assert group.current_owner == owners[0].user_id
        assert group.created_by == users[0]


@pytest.mark.asyncio
@pytest.mark.parametrize('operation', ['delete', 'demote', 'second_owner', 'new_ownerless'])
@pytest.mark.parametrize('soft_deleted', [False, True])
async def test_constraints_reject_zero_or_multiple_owners(sessions, operation, soft_deleted):
    gid, users = await setup_members(sessions)
    async with sessions() as session:
        if soft_deleted:
            group = await session.get(Group, UUID(gid))
            group.deleted_at = datetime.now(timezone.utc)
            await session.commit()
        with pytest.raises(IntegrityError):
            if operation == 'new_ownerless':
                session.add(Group(group_name='Invalid', group_type='private',
                    created_by=users[0], current_owner=users[0], max_members=5,
                    created_at=datetime.now(timezone.utc),
                    deleted_at=datetime.now(timezone.utc) if soft_deleted else None))
            else:
                target = users[1] if operation == 'second_owner' else users[0]
                row = await session.scalar(select(Membership).where(
                    Membership.group_id == UUID(gid), Membership.user_id == target))
                if operation == 'delete':
                    await session.delete(row)
                else:
                    row.member_role = MemberRole.OWNER if operation == 'second_owner' else MemberRole.ADMIN
            await session.commit()
        await session.rollback()
