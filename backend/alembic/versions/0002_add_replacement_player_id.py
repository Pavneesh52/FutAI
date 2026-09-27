"""add replacement_player_id to events

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-27

Adds a nullable FK column `replacement_player_id` to the `events` table.
For substitution events, this records the player who came ON (the existing
`player_id` is the player going OFF).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column("replacement_player_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_events_replacement_player_id_players",
        "events",
        "players",
        ["replacement_player_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_events_replacement_player_id_players", "events", type_="foreignkey")
    op.drop_column("events", "replacement_player_id")
