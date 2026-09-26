"""Integration coverage for PostgreSQL Study Group persistence."""

import os

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domains.auth.infrastructure.repository import (
    PostgreSQLAuthRepository,
)
from app.domains.study_groups.domain.models import (
    MyGroupsFilter,
    StudyGroupMemberRole,
    StudyGroupVisibility,
)
from app.domains.study_groups.infrastructure.repository import (
    PostgreSQLStudyGroupRepository,
)
from app.models.orm_models import Group


TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    (
        "postgresql+psycopg://"
        "spc_backend:spc_local_password@postgres:5432/spc_auth_test"
    ),
)


async def clear_tables(engine) -> None:
    """Reset test records without altering the database schema."""

    async with engine.begin() as connection:
        await connection.execute(
            text(
                """
                TRUNCATE TABLE memberships, groups, users
                RESTART IDENTITY CASCADE
                """
            )
        )


@pytest.mark.asyncio
async def test_postgresql_study_group_workflow() -> None:
    """Persist create, discovery, join, visibility, leave, and deletion."""

    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        await clear_tables(engine)

        async with session_factory() as session:
            auth = PostgreSQLAuthRepository(session)
            owner = await auth.create_user(
                full_name="Group Owner",
                email="postgres-group-owner@example.com",
                hashed_password="hash",
            )
            member = await auth.create_user(
                full_name="Group Member",
                email="postgres-group-member@example.com",
                hashed_password="hash",
            )

        async with session_factory() as session:
            groups = PostgreSQLStudyGroupRepository(session)
            public_group = await groups.create_group(
                name="PostgreSQL Revision",
                description="Database-backed study group",
                visibility=StudyGroupVisibility.PUBLIC,
                created_by=owner.id,
                max_members=5,
            )
            private_group = await groups.create_group(
                name="Private Revision",
                description=None,
                visibility=StudyGroupVisibility.PRIVATE,
                created_by=owner.id,
                max_members=5,
            )
            assert public_group.member_count == 1
            assert public_group.membership_role == StudyGroupMemberRole.ADMIN

        async with session_factory() as session:
            groups = PostgreSQLStudyGroupRepository(session)
            discovered, total = (
                await groups.list_discoverable_public_groups(
                    user_id=member.id,
                    offset=0,
                    limit=20,
                    search="PostgreSQL",
                )
            )
            assert total == 1
            assert discovered[0].is_member is False
            assert await groups.get_group_for_user(
                group_id=private_group.group.group_id,
                user_id=member.id,
            ) is None

            membership = await groups.create_membership(
                group_id=public_group.group.group_id,
                user_id=member.id,
                role=StudyGroupMemberRole.MEMBER,
                joined_at=public_group.group.created_at,
            )
            assert membership.role == StudyGroupMemberRole.MEMBER

            mine, mine_total = await groups.list_user_groups(
                user_id=member.id,
                group_filter=MyGroupsFilter.ALL,
                offset=0,
                limit=20,
            )
            assert mine_total == 1
            assert mine[0].group.group_id == public_group.group.group_id

            assert await groups.delete_membership(
                group_id=public_group.group.group_id,
                user_id=member.id,
            ) is True
            assert await groups.soft_delete_group(
                group_id=public_group.group.group_id,
                deleted_at=public_group.group.created_at,
            ) is True

        async with session_factory() as session:
            deleted = await session.scalar(
                select(Group).where(
                    Group.group_id == public_group.group.group_id
                )
            )
            assert deleted is not None
            assert deleted.deleted_at is not None

    finally:
        await engine.dispose()
