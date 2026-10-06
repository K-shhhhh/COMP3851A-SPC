"""Ownership transactions using the real repository and a local SQL database.

SQLite exercises constraints and rollback; PostgreSQL integration tests cover
row locking. Only dialect-specific DDL is adapted in this fixture.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Computed, Integer, MetaData, create_engine, select, text
from sqlalchemy.dialects.postgresql import dialect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, configure_mappers
from sqlalchemy.schema import AddConstraint, CreateIndex

from app.models.orm_models import Group, Membership, MemberRole, User, UserRole
from app.domains.study_groups.domain.models import StudyGroupMemberRole, StudyGroupVisibility, MyGroupsFilter
from app.domains.study_groups.domain.exceptions import (
    InvalidStudyGroupError, StudyGroupPermissionDeniedError, StudyGroupMembershipNotFoundError,
)
from app.domains.study_groups.infrastructure.repository import PostgreSQLStudyGroupRepository
from app.domains.auth.infrastructure.repository import PostgreSQLAuthRepository
from app.domains.study_groups.application.services import StudyGroupService


class AsyncSessionAdapter:
    """Awaitable facade over SQLite's synchronous session for repository tests."""

    def __init__(self, session):
        self.session = session

    def add(self, row):
        self.session.add(row)

    def __getattr__(self, name):
        async def call(*args, **kwargs):
            return getattr(self.session, name)(*args, **kwargs)
        return call


@pytest.fixture
def db():
    configure_mappers()
    metadata = MetaData()
    for model in (User, Group, Membership):
        model.__table__.to_metadata(metadata)
    memberships = metadata.tables['memberships']
    memberships.c.membership_id.type = Integer()
    owner_column = metadata.tables['groups'].c.active_owner_role
    computed = Computed("'owner'", persisted=True)
    owner_column.computed = owner_column.server_default = owner_column.server_onupdate = computed
    for index in memberships.indexes:
        if index.name == 'uq_memberships_group_owner':
            index.dialect_options['sqlite']['where'] = text("member_role = 'owner'")
    engine = create_engine('sqlite://')
    with engine.connect() as connection:
        connection.exec_driver_sql('PRAGMA foreign_keys=ON')
        metadata.create_all(connection)
        connection.commit()
        with Session(connection, expire_on_commit=False) as session:
            ids = [uuid4() for _ in range(3)]
            session.add_all([User(user_id=value, email=f'{value}@example.com',
                fullname='Student', password_hash='test', user_role=UserRole.STUDENT,
                created_at=datetime.now(timezone.utc)) for value in ids])
            session.commit()
            yield session, PostgreSQLStudyGroupRepository(AsyncSessionAdapter(session)), ids
    engine.dispose()


async def setup_group(db):
    session, repo, ids = db
    group = await repo.create_group(name='Ownership', description=None,
        visibility=StudyGroupVisibility.PRIVATE, created_by=str(ids[0]), max_members=5)
    gid = group.group.group_id
    for uid in ids[1:]:
        await repo.create_membership(group_id=gid, user_id=str(uid),
            role=StudyGroupMemberRole.MEMBER, joined_at=datetime.now(timezone.utc))
    return session, repo, ids, gid


@pytest.mark.asyncio
@pytest.mark.parametrize('visibility', [StudyGroupVisibility.PUBLIC, StudyGroupVisibility.PRIVATE])
async def test_creation_sets_creator_and_current_owner(db, visibility):
    session, repo, ids = db
    created = await repo.create_group(name='New group', description=None,
        visibility=visibility, created_by=str(ids[0]), max_members=5)
    stored = session.get(Group, UUID(created.group.group_id))
    assert stored.created_by == stored.current_owner == ids[0]
    membership = await repo.get_membership(group_id=created.group.group_id, user_id=str(ids[0]))
    assert membership.role == StudyGroupMemberRole.OWNER


@pytest.mark.asyncio
async def test_each_registration_creates_its_own_personal_group(db):
    from app.models.orm_models import GroupType
    session, _, _ = db
    auth = PostgreSQLAuthRepository(AsyncSessionAdapter(session))
    group_ids = set()
    for i in range(2):
        user = await auth.create_user(full_name=f'New Student {i}',
            email=f'new-student-{i}@example.com', hashed_password='test-hash')
        uid = UUID(user.id)
        groups = session.scalars(select(Group).where(Group.created_by == uid)).all()
        assert len(groups) == 1
        group = groups[0]
        assert group.group_type == GroupType.PERSONAL
        assert group.created_by == group.current_owner == uid
        assert group.max_members == 1
        memberships = session.scalars(select(Membership).where(Membership.group_id == group.group_id)).all()
        assert len(memberships) == 1
        assert memberships[0].user_id == uid and memberships[0].member_role == MemberRole.OWNER
        group_ids.add(group.group_id)
    assert len(group_ids) == 2


@pytest.mark.asyncio
async def test_leave_deletes_membership_and_owner_must_transfer_first(db):
    session, repo, ids, gid = await setup_group(db)
    service = StudyGroupService(repo)
    with pytest.raises(StudyGroupPermissionDeniedError):
        await service.leave_group(group_id=gid, user_id=str(ids[0]))
    await service.leave_group(group_id=gid, user_id=str(ids[2]))
    assert session.scalar(select(Membership).where(
        Membership.group_id == UUID(gid), Membership.user_id == ids[2])) is None
    await service.transfer_ownership(group_id=gid, requester_user_id=str(ids[0]), target_user_id=str(ids[1]))
    assert (await repo.get_membership(group_id=gid, user_id=str(ids[0]))).role == StudyGroupMemberRole.ADMIN
    await service.leave_group(group_id=gid, user_id=str(ids[0]))
    assert session.scalar(select(Membership).where(
        Membership.group_id == UUID(gid), Membership.user_id == ids[0])) is None
    assert session.get(Group, UUID(gid)).created_by == ids[0]
    assert 'deleted_at' not in Membership.__table__.c


def test_owner_enum_and_postgresql_constraints():
    role_type = Membership.__table__.c.member_role.type
    assert role_type.result_processor(dialect(), None)('owner') == MemberRole.OWNER
    index = next(i for i in Membership.__table__.indexes if i.name == 'uq_memberships_group_owner')
    assert "WHERE member_role = 'owner'" in str(CreateIndex(index).compile(dialect=dialect()))
    fk = next(c for c in Group.__table__.foreign_key_constraints if c.name == 'fk_groups_active_owner')
    ddl = str(AddConstraint(fk).compile(dialect=dialect()))
    assert 'DEFERRABLE INITIALLY DEFERRED' in ddl
    assert '(group_id, current_owner, active_owner_role)' in ddl


@pytest.mark.asyncio
async def test_transfer_and_creator_departure_preserve_history(db):
    session, repo, ids, gid = await setup_group(db)
    await repo.update_membership_role(group_id=gid, user_id=str(ids[1]), role=StudyGroupMemberRole.ADMIN)
    old, new = await repo.transfer_ownership(group_id=gid, current_owner_id=str(ids[0]), new_owner_id=str(ids[1]))
    assert (old.role, new.role) == (StudyGroupMemberRole.ADMIN, StudyGroupMemberRole.OWNER)
    stored = session.get(Group, UUID(gid))
    assert stored.created_by == ids[0] and stored.current_owner == ids[1]
    assert (await repo.get_group_for_user(group_id=gid, user_id=str(ids[1]))).is_owner
    assert not (await repo.get_group_for_user(group_id=gid, user_id=str(ids[0]))).is_owner
    assert await repo.delete_membership(group_id=gid, user_id=str(ids[0]))
    assert await repo.get_group_for_user(group_id=gid, user_id=str(ids[0])) is None
    assert (await repo.list_user_groups(user_id=str(ids[0]), group_filter=MyGroupsFilter.ALL, offset=0, limit=20))[1] == 0
    assert (await repo.list_user_groups(user_id=str(ids[1]), group_filter=MyGroupsFilter.OWNED, offset=0, limit=20))[1] == 1
    assert session.get(Group, UUID(gid)).created_by == ids[0]


@pytest.mark.asyncio
@pytest.mark.parametrize('failure_role', ['admin', 'owner'])
async def test_transfer_rolls_back_if_either_update_fails(db, failure_role):
    session, repo, ids, gid = await setup_group(db)
    # Reject the first demotion or second promotion after successful setup.
    session.execute(text(f"CREATE TRIGGER reject_role BEFORE UPDATE OF member_role ON memberships "
        f"WHEN NEW.member_role = '{failure_role}' BEGIN SELECT RAISE(ABORT, 'forced failure'); END"))
    session.commit()
    with pytest.raises(IntegrityError):
        await repo.transfer_ownership(group_id=gid, current_owner_id=str(ids[0]), new_owner_id=str(ids[1]))
    assert (await repo.get_membership(group_id=gid, user_id=str(ids[0]))).role == StudyGroupMemberRole.OWNER
    assert (await repo.get_membership(group_id=gid, user_id=str(ids[1]))).role == StudyGroupMemberRole.MEMBER
    assert session.get(Group, UUID(gid)).current_owner == ids[0]


@pytest.mark.asyncio
async def test_role_updates_and_owner_protection(db):
    _, repo, ids, gid = await setup_group(db)
    for role in (StudyGroupMemberRole.ADMIN, StudyGroupMemberRole.MEMBER):
        assert (await repo.update_membership_role(group_id=gid, user_id=str(ids[1]), role=role)).role == role
    with pytest.raises(InvalidStudyGroupError):
        await repo.update_membership_role(group_id=gid, user_id=str(ids[1]), role=StudyGroupMemberRole.OWNER)
    with pytest.raises(StudyGroupPermissionDeniedError):
        await repo.update_membership_role(group_id=gid, user_id=str(ids[0]), role=StudyGroupMemberRole.ADMIN)
    with pytest.raises(StudyGroupPermissionDeniedError):
        await repo.delete_membership(group_id=gid, user_id=str(ids[0]))


@pytest.mark.asyncio
@pytest.mark.parametrize('invalid_target', ['missing', 'inactive', 'deleted', 'self', 'wrong_owner'])
async def test_invalid_transfer_preserves_owner(db, invalid_target):
    session, repo, ids, gid = await setup_group(db)
    target, current = ids[1], ids[0]
    error = StudyGroupMembershipNotFoundError
    if invalid_target == 'missing':
        target = uuid4()
    elif invalid_target == 'inactive':
        from app.models.orm_models import ActivityStatus
        session.get(User, target).status = ActivityStatus.DEACTIVATED
    elif invalid_target == 'deleted':
        session.get(User, target).deleted_at = datetime.now(timezone.utc)
    elif invalid_target == 'self':
        target, error = current, InvalidStudyGroupError
    else:
        current, error = ids[2], StudyGroupPermissionDeniedError
    session.commit()
    with pytest.raises(error):
        await repo.transfer_ownership(group_id=gid, current_owner_id=str(current), new_owner_id=str(target))
    assert (await repo.get_membership(group_id=gid, user_id=str(ids[0]))).role == StudyGroupMemberRole.OWNER


@pytest.mark.asyncio
@pytest.mark.parametrize('operation', ['second_owner', 'delete_owner', 'demote_owner', 'wrong_pointer', 'new_ownerless'])
async def test_database_rejects_invalid_ownership(db, operation):
    session, repo, ids, gid = await setup_group(db)
    with pytest.raises(IntegrityError):
        if operation == 'new_ownerless':
            session.add(Group(group_name='Invalid', group_type='private', created_by=ids[0],
                current_owner=ids[0], max_members=5, created_at=datetime.now(timezone.utc)))
        elif operation == 'wrong_pointer':
            session.get(Group, UUID(gid)).current_owner = ids[1]
        else:
            user_id = ids[1] if operation == 'second_owner' else ids[0]
            row = session.scalar(select(Membership).where(Membership.group_id == UUID(gid), Membership.user_id == user_id))
            if operation == 'delete_owner':
                session.delete(row)
            else:
                row.member_role = MemberRole.OWNER if operation == 'second_owner' else MemberRole.ADMIN
        session.commit()
    # SQLite leaves a transaction open after a deferred COMMIT failure;
    # PostgreSQL aborts it. Clear that DBAPI state before resetting the session.
    session.get_bind().connection.rollback()
    session.rollback()
    assert (await repo.get_membership(group_id=gid, user_id=str(ids[0]))).role == StudyGroupMemberRole.OWNER


@pytest.mark.asyncio
async def test_soft_deleted_group_owner_cannot_leave(db):
    session, repo, ids, gid = await setup_group(db)
    group = session.get(Group, UUID(gid))
    group.deleted_at = datetime.now(timezone.utc)
    session.commit()
    with pytest.raises(StudyGroupPermissionDeniedError):
        await repo.delete_membership(group_id=gid, user_id=str(ids[0]))
    with pytest.raises(IntegrityError):
        owner = session.scalar(select(Membership).where(Membership.group_id == UUID(gid), Membership.user_id == ids[0]))
        session.delete(owner)
        session.commit()
    session.get_bind().connection.rollback()
    session.rollback()
    remaining_owner = session.scalar(select(Membership).where(
        Membership.group_id == UUID(gid), Membership.user_id == ids[0]))
    assert remaining_owner.member_role == MemberRole.OWNER
    assert session.get(Group, UUID(gid)).deleted_at is not None


@pytest.mark.asyncio
async def test_memory_adapter_protects_soft_deleted_group_owner():
    from app.domains.study_groups.infrastructure.memory_repository import InMemoryStudyGroupRepository
    repo = InMemoryStudyGroupRepository()
    created = await repo.create_group(name='Archived', description=None,
        visibility=StudyGroupVisibility.PRIVATE, created_by='creator', max_members=5)
    gid = created.group.group_id
    await repo.soft_delete_group(group_id=gid, deleted_at=datetime.now(timezone.utc))
    with pytest.raises(StudyGroupPermissionDeniedError):
        await repo.delete_membership(group_id=gid, user_id='creator')
