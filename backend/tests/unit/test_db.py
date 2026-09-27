"""Tests for the database probe.

These run without a database: both cases assert that the probe reports a status
rather than raising, which is what keeps /health honest and crash-free (rule R5).
"""

from __future__ import annotations

from app.core.db import check_database

from tests.conftest import offline_settings


async def test_missing_database_url_is_reported_not_raised() -> None:
    assert await check_database(offline_settings(database_url="")) == "not_configured"


async def test_url_without_an_async_driver_is_reported_not_raised() -> None:
    """A misconfigured URL must degrade, not take the process down."""
    settings = offline_settings(
        database_url="postgresql://app:app@localhost:5432/football",
        db_health_timeout_seconds=1.0,
    )

    assert await check_database(settings) == "unavailable"


async def test_unreachable_database_is_reported_not_raised() -> None:
    """Port 1 on loopback refuses instantly, so this never leaves the machine."""
    settings = offline_settings(
        database_url="postgresql+psycopg://app:app@127.0.0.1:1/football",
        db_health_timeout_seconds=1.0,
    )

    assert await check_database(settings) == "unavailable"
