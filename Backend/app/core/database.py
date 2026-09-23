from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def _async_database_url(url: str) -> str:
    """ Ensures PostgreSQL URLs to the psycopg 3 SQLAlchemy dialect. """
    if url.startswith("postgresql://"):
        return url.replace(
            "postgresql://",
            "postgresql+psycopg://",
            1,
        )

    return url


class Database:
    """Own the application-wide engine and session factory."""

    def __init__(self, url: str) -> None:
        self.engine: AsyncEngine = create_async_engine(
            _async_database_url(url),
            echo=settings.DEBUG,
            pool_pre_ping=True,
        )

        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    async def connect(self) -> None:
        """Verify that the database is reachable."""
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def disconnect(self) -> None:
        """Close the engine and dispose of pooled connections."""
        await self.engine.dispose()

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.session_factory() as session:
            yield session


database = Database(settings.DATABASE_URL)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """ FastAPI dependency providing one AsyncSession per request. """
    async with database.session() as session:
        yield session