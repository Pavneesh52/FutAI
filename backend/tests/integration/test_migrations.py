"""Migration 0001 against a real database.

Two things only a live database can prove: that `downgrade` actually reverses `upgrade`
(a broken down-revision is invisible until the day you need to roll back), and that the
ORM models and the migration still describe the same schema -- the drift check is what
`alembic check` runs, and a silent divergence would only show up on a fresh deploy.
"""

from __future__ import annotations

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from app.models import Base
from sqlalchemy.engine import Engine

from tests.integration.conftest import (
    TABLES,
    downgrade_base,
    requires_postgres,
    table_names,
    upgrade_head,
)

pytestmark = [pytest.mark.integration, requires_postgres]


def test_migration_is_reversible_and_matches_the_models(sync_engine: Engine) -> None:
    upgrade_head()
    assert set(TABLES) <= table_names(sync_engine)
    # The version table is Alembic's own bookkeeping, not part of our metadata.
    assert "alembic_version" in table_names(sync_engine)

    downgrade_base()
    assert not (set(TABLES) & table_names(sync_engine))

    # Leave the database migrated: everything after this test assumes the schema exists.
    upgrade_head()
    assert set(TABLES) <= table_names(sync_engine)


def test_no_model_drift_after_upgrade(sync_engine: Engine) -> None:
    upgrade_head()

    with sync_engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        diff = compare_metadata(context, Base.metadata)

    assert diff == [], f"models and migration 0001 have diverged: {diff}"
