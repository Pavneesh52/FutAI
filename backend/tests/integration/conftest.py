"""Fixtures for the integration tests.

These talk to the database in `DATABASE_URL` and *mutate* it (migrations are applied and
reverted, tables are truncated). That is the docker-compose Postgres; never point them at
anything you care about.

    docker compose up -d
    cd backend && uv run pytest tests/integration

When the database is unreachable every test in this package skips instead of failing, so a
plain `pytest` run stays green on a machine without Postgres.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from app.core.config import Settings, get_settings
from app.core.db import check_database, dispose_engine, session_scope
from app.etl.statsbomb import load_match
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession

BACKEND_DIR = Path(__file__).resolve().parents[2]
FIXTURES = BACKEND_DIR / "tests" / "fixtures" / "statsbomb"

#: Every table the initial migration creates, in FK-safe truncation order.
TABLES = (
    "teams",
    "players",
    "matches",
    "events",
    "team_match_stats",
    "player_match_stats",
    "formations",
)

FINAL = 3943077  # Argentina 1-0 Colombia, after extra time
QUARTER_FINAL = 3942228  # Argentina 1-1 Ecuador, won on penalties


def _probe_database() -> bool:
    """Check the configured database once, at import time."""

    async def probe() -> bool:
        try:
            return await check_database(get_settings()) == "ok"
        finally:
            await dispose_engine()

    return asyncio.run(probe())


DATABASE_READY = _probe_database()

requires_postgres = pytest.mark.skipif(
    not DATABASE_READY,
    reason="Postgres is unreachable; start it with `docker compose up -d`.",
)


@pytest.fixture(scope="session", autouse=True)
def migrated_schema() -> None:
    """Ensure the schema exists before any data test, whatever the file order.

    `test_etl_load.py` sorts before `test_migrations.py`, and a fresh database volume has
    no tables at all, so the schema is applied here (idempotently) rather than relying on
    the migration test having run first.
    """
    if DATABASE_READY:
        upgrade_head()


@pytest.fixture(scope="session")
def settings() -> Settings:
    """The project settings, read from `.env` as everywhere else."""
    return get_settings()


@pytest.fixture(scope="session")
def sync_engine(settings: Settings) -> Iterator[Engine]:
    """A synchronous engine, for Alembic and for raw-SQL assertions."""
    engine = create_engine(settings.database_url)
    yield engine
    engine.dispose()


@pytest.fixture
async def session(settings: Settings) -> AsyncIterator[AsyncSession]:
    """A session that does not commit on exit, so a test's writes stay its own."""
    async with session_scope(settings) as open_session:
        yield open_session


def alembic_config() -> Config:
    """Alembic config pointed at `backend/alembic`, independent of the cwd."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return config


def upgrade_head() -> None:
    command.upgrade(alembic_config(), "head")


def downgrade_base() -> None:
    command.downgrade(alembic_config(), "base")


def table_names(engine: Engine) -> set[str]:
    """Tables currently in the `public` schema."""
    with engine.connect() as connection:
        rows = connection.execute(
            text("select table_name from information_schema.tables where table_schema = 'public'")
        )
        return {str(row[0]) for row in rows}


async def truncate_all(session: AsyncSession) -> None:
    """Empty every table so a test's row counts are deterministic."""
    await session.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
    await session.commit()


async def table_counts(session: AsyncSession) -> dict[str, int]:
    """Row count per table, for the idempotency check."""
    counts: dict[str, int] = {}
    for table in TABLES:
        total = await session.scalar(text(f"select count(*) from {table}"))
        counts[table] = int(total or 0)
    return counts


def load_fixture(kind: str, match_id: int) -> Any:
    with (FIXTURES / kind / f"{match_id}.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def load_fixture_matches() -> list[dict[str, Any]]:
    """The fixture season file, which holds exactly the two committed matches."""
    path = FIXTURES / "matches" / "223" / "282.json"
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


async def load_fixture_match(session: AsyncSession, match_id: int) -> dict[str, int]:
    """Load one committed fixture through the real ETL, exactly as the CLI does."""
    raw_match = next(
        entry for entry in load_fixture_matches() if int(entry["match_id"]) == match_id
    )
    return await load_match(
        session,
        raw_match,
        load_fixture("events", match_id),
        load_fixture("lineups", match_id),
    )
