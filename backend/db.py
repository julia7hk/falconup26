"""
SQLAlchemy Async Session

Database connection and session management.
"""

import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_raw_url = os.environ.get("DATABASE_URL", "")

# Defer engine creation so importing db.py doesn't crash in environments
# without DATABASE_URL (e.g. CI test collection, frontend-only builds).
engine = None
async_session = None

if _raw_url:
    # asyncpg requires the +asyncpg driver suffix
    _async_url = _raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(_async_url, pool_pre_ping=True)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session():
    """FastAPI dependency — yields an async database session."""
    if async_session is None:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    async with async_session() as session:
        yield session
