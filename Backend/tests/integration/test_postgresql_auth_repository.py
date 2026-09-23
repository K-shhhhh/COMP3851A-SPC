"""Integration tests for PostgreSQL authentication persistence.

These tests use a dedicated test database. They verify SQLAlchemy mappings,
repository operations, and the transactional creation of the user, personal
group, and initial membership.
"""

import os

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from app.domains.auth.domain.exceptions import (
    EmailAlreadyRegisteredError,
)
from app.domains.auth.infrastructure.repository import (
    PostgreSQLAuthRepository,
)
from app.models.orm_models import (
    Group,
    GroupType,
    Membership,
    User,
)


TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    (
        "postgresql+psycopg://"
        "spc_backend:spc_local_password@postgres:5432/spc_auth_test"
    ),
)


async def clear_authentication_tables(engine) -> None:
    """Remove authentication test records without dropping the schema."""

    async with engine.begin() as connection:
        await connection.execute(
            text(
                """
                TRUNCATE TABLE
                    memberships,
                    groups,
                    users
                RESTART IDENTITY CASCADE
                """
            )
        )


@pytest.mark.asyncio
async def test_registration_creates_personal_group_and_membership() -> None:
    """Registration must atomically create all personal-account records."""

    engine = create_async_engine(
        TEST_DATABASE_URL,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    try:
        await clear_authentication_tables(engine)

        async with session_factory() as session:
            repository = PostgreSQLAuthRepository(session)

            created_user = await repository.create_user(
                full_name="Database Test Student",
                email="database-test@example.com",
                hashed_password="test-password-hash",
            )

            assert created_user.id
            assert created_user.email == "database-test@example.com"
            assert created_user.role == "student"
            assert created_user.is_active is True

        async with session_factory() as verification_session:
            user_count = await verification_session.scalar(
                select(func.count()).select_from(User)
            )
            group_count = await verification_session.scalar(
                select(func.count()).select_from(Group)
            )
            membership_count = await verification_session.scalar(
                select(func.count()).select_from(Membership)
            )

            personal_group = await verification_session.scalar(
                select(Group).where(
                    Group.group_type == GroupType.PERSONAL
                )
            )

            assert user_count == 1
            assert group_count == 1
            assert membership_count == 1

            assert personal_group is not None
            assert str(personal_group.created_by) == created_user.id
            assert str(personal_group.current_admin) == created_user.id
            assert personal_group.group_name == created_user.id
            assert personal_group.max_members == 1

    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_duplicate_email_is_rejected() -> None:
    """The database unique constraint must reject duplicate accounts."""

    engine = create_async_engine(
        TEST_DATABASE_URL,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    try:
        await clear_authentication_tables(engine)

        async with session_factory() as session:
            repository = PostgreSQLAuthRepository(session)

            await repository.create_user(
                full_name="First Student",
                email="duplicate@example.com",
                hashed_password="first-password-hash",
            )

            with pytest.raises(EmailAlreadyRegisteredError):
                await repository.create_user(
                    full_name="Second Student",
                    email="duplicate@example.com",
                    hashed_password="second-password-hash",
                )

    finally:
        await engine.dispose()