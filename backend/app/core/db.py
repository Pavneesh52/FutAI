"""Database engine plus a timeout-bounded health probe.

Deliberately minimal: ORM models, sessions and migrations arrive in Phase 1. All this
module owns for now is a lazily created async engine and a probe that can never hang
or raise (rule R4 + rule R5).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings

DatabaseStatus = Literal["ok", "unavailable", "not_configured"]

_PROBE = text("SELECT 1")

_engine: AsyncEngine | None = None
_engine_url: str | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine(settings: Settings) -> AsyncEngine:
    """Return a cached async engine for the configured URL.

    Recreated if the configured URL changes, which keeps tests and config reloads sane.
    """
    global _engine, _engine_url, _session_factory
    if _engine is None or _engine_url != settings.database_url:
        _engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        _engine_url = settings.database_url
        # The old factory would keep handing out sessions bound to the old engine.
        _session_factory = None
    return _engine


def get_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    """Return a session factory bound to the current engine."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(settings), expire_on_commit=False)
    return _session_factory


@asynccontextmanager
async def session_scope(settings: Settings) -> AsyncIterator[AsyncSession]:
    """Open a session for scripts (the API gets one per request via `app.api.deps`).

    Does not commit for you: callers decide their transaction boundaries, so a failed
    match load cannot leave a half-written season behind.
    """
    factory = get_session_factory(settings)
    async with factory() as session:
        yield session


async def dispose_engine() -> None:
    """Close pooled connections. Called on application shutdown."""
    global _engine, _engine_url, _session_factory
    engine, _engine = _engine, None
    _engine_url = None
    _session_factory = None
    if engine is not None:
        await engine.dispose()


async def check_database(settings: Settings) -> DatabaseStatus:
    """Probe the database, degrading to a status instead of raising."""
    if not settings.database_url:
        return "not_configured"

    try:
        async with asyncio.timeout(settings.db_health_timeout_seconds):
            engine = get_engine(settings)
            async with engine.connect() as connection:
                await connection.execute(_PROBE)
    except (SQLAlchemyError, OSError, TimeoutError, ImportError):
        # ImportError covers a URL missing its async driver (e.g. `postgresql://`
        # instead of `postgresql+psycopg://`), which SQLAlchemy raises while resolving
        # the DBAPI. Misconfiguration must degrade, not crash the health endpoint.
        return "unavailable"

    return "ok"
