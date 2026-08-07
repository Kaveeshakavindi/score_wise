from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import Settings


class Base(DeclarativeBase):
    pass


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _to_async_url(database_url: str) -> str:
    """DATABASE_URL is shared with the sync CLI app (chatbot/db/conn.py, which
    uses plain psycopg and needs a driverless `postgresql://` URL), so the API
    normalizes to the asyncpg driver here rather than requiring a second env
    var or a `+asyncpg`-suffixed value in .env."""
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return database_url


def init_engine(settings: Settings) -> AsyncEngine:
    """Creates the process-wide async engine + pooled connection factory.
    Any worker can serve any request (§14) — the engine holds no per-request state."""
    global _engine, _session_factory
    _engine = create_async_engine(_to_async_url(settings.database_url), pool_pre_ping=True, future=True)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    return _engine


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Database engine not initialized; call init_engine() at startup.")
    return _session_factory


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, committed on success,
    rolled back on exception."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
