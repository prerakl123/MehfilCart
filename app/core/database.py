"""
Async SQLAlchemy engine and session factory.
Provides the `get_db` async generator for FastAPI dependency injection.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# Silence the verbose SQLAlchemy SQL echo; keep only warnings+
logging.getLogger("sqlalchemy.engine").setLevel(
    logging.DEBUG if settings.SQL_ECHO else logging.WARNING
)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,           # we control logging via the Python logger above
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Declarative base class for all ORM models."""
    pass


async def get_db() -> AsyncSession:
    """Yield an async database session. Used as a FastAPI dependency."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
