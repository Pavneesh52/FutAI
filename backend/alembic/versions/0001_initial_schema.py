"""initial schema: teams, players, matches, events, stats, formations

Revision ID: 0001
Revises:
Create Date: 2026-09-21

Constraint and index names match the naming convention in `app.models.base`, so
`alembic check` reports no drift against the models.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "teams",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("founded_year", sa.Integer(), nullable=True),
        sa.Column("source_id", sa.String(length=120), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_teams"),
        sa.UniqueConstraint("source_id", name="uq_teams_source_id"),
    )
    op.create_index("ix_teams_name", "teams", ["name"])

    op.create_table(
        "players",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("team_id", sa.BigInteger(), nullable=True),
        sa.Column("position", sa.String(length=80), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("source_id", sa.String(length=120), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], name="fk_players_team_id_teams"),
        sa.PrimaryKeyConstraint("id", name="pk_players"),
        sa.UniqueConstraint("source_id", name="uq_players_source_id"),
    )
    op.create_index("ix_players_name", "players", ["name"])

    op.create_table(
        "matches",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("home_team_id", sa.BigInteger(), nullable=False),
        sa.Column("away_team_id", sa.BigInteger(), nullable=False),
        sa.Column("competition", sa.String(length=120), nullable=False),
        sa.Column("season", sa.String(length=40), nullable=False),
        sa.Column("match_date", sa.Date(), nullable=False),
        sa.Column("home_score", sa.Integer(), nullable=True),
        sa.Column("away_score", sa.Integer(), nullable=True),
        sa.Column("source_id", sa.String(length=120), nullable=False),
        sa.ForeignKeyConstraint(
            ["home_team_id"], ["teams.id"], name="fk_matches_home_team_id_teams"
        ),
        sa.ForeignKeyConstraint(
            ["away_team_id"], ["teams.id"], name="fk_matches_away_team_id_teams"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_matches"),
        sa.UniqueConstraint("source_id", name="uq_matches_source_id"),
    )

    op.create_table(
        "events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.BigInteger(), nullable=False),
        sa.Column("minute", sa.Integer(), nullable=False),
        sa.Column("second", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("team_id", sa.BigInteger(), nullable=False),
        sa.Column("player_id", sa.BigInteger(), nullable=True),
        sa.Column("x", sa.Float(), nullable=True),
        sa.Column("y", sa.Float(), nullable=True),
        sa.Column("outcome", sa.String(length=60), nullable=True),
        sa.Column("xg", sa.Float(), nullable=True),
        sa.Column("related_event_id", sa.BigInteger(), nullable=True),
        sa.Column("possession_id", sa.Integer(), nullable=True),
        sa.Column("source_id", sa.String(length=120), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"], name="fk_events_match_id_matches"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], name="fk_events_team_id_teams"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], name="fk_events_player_id_players"),
        sa.PrimaryKeyConstraint("id", name="pk_events"),
        sa.UniqueConstraint("source_id", name="uq_events_source_id"),
    )
    op.create_index("ix_events_event_type", "events", ["event_type"])
    op.create_index("ix_events_match_id_minute", "events", ["match_id", "minute"])

    op.create_table(
        "team_match_stats",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.BigInteger(), nullable=False),
        sa.Column("team_id", sa.BigInteger(), nullable=False),
        sa.Column("possession_pct", sa.Float(), nullable=True),
        sa.Column("xg", sa.Float(), nullable=True),
        sa.Column("shots", sa.Integer(), nullable=True),
        sa.Column("shots_on_target", sa.Integer(), nullable=True),
        sa.Column("passes", sa.Integer(), nullable=True),
        sa.Column("pass_accuracy", sa.Float(), nullable=True),
        sa.Column("ppda", sa.Float(), nullable=True),
        sa.Column("field_tilt", sa.Float(), nullable=True),
        sa.Column("formation", sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(
            ["match_id"], ["matches.id"], name="fk_team_match_stats_match_id_matches"
        ),
        sa.ForeignKeyConstraint(
            ["team_id"], ["teams.id"], name="fk_team_match_stats_team_id_teams"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_team_match_stats"),
        sa.UniqueConstraint("match_id", "team_id", name="uq_team_match_stats_match_id_team_id"),
    )

    op.create_table(
        "player_match_stats",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.BigInteger(), nullable=False),
        sa.Column("player_id", sa.BigInteger(), nullable=False),
        sa.Column("team_id", sa.BigInteger(), nullable=False),
        sa.Column("minutes_played", sa.Integer(), nullable=True),
        sa.Column("goals", sa.Integer(), nullable=True),
        sa.Column("assists", sa.Integer(), nullable=True),
        sa.Column("xg", sa.Float(), nullable=True),
        sa.Column("xa", sa.Float(), nullable=True),
        sa.Column("passes", sa.Integer(), nullable=True),
        sa.Column("pass_accuracy", sa.Float(), nullable=True),
        sa.Column("shots", sa.Integer(), nullable=True),
        sa.Column("tackles", sa.Integer(), nullable=True),
        sa.Column("position_played", sa.String(length=80), nullable=True),
        sa.ForeignKeyConstraint(
            ["match_id"], ["matches.id"], name="fk_player_match_stats_match_id_matches"
        ),
        sa.ForeignKeyConstraint(
            ["player_id"], ["players.id"], name="fk_player_match_stats_player_id_players"
        ),
        sa.ForeignKeyConstraint(
            ["team_id"], ["teams.id"], name="fk_player_match_stats_team_id_teams"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_player_match_stats"),
        sa.UniqueConstraint(
            "match_id", "player_id", name="uq_player_match_stats_match_id_player_id"
        ),
    )

    op.create_table(
        "formations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.BigInteger(), nullable=False),
        sa.Column("team_id", sa.BigInteger(), nullable=False),
        sa.Column("formation_string", sa.String(length=20), nullable=False),
        sa.Column("period", sa.Integer(), nullable=False),
        sa.Column("start_minute", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["match_id"], ["matches.id"], name="fk_formations_match_id_matches"
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], name="fk_formations_team_id_teams"),
        sa.PrimaryKeyConstraint("id", name="pk_formations"),
    )


def downgrade() -> None:
    op.drop_table("formations")
    op.drop_table("player_match_stats")
    op.drop_table("team_match_stats")
    op.drop_index("ix_events_match_id_minute", table_name="events")
    op.drop_index("ix_events_event_type", table_name="events")
    op.drop_table("events")
    op.drop_table("matches")
    op.drop_index("ix_players_name", table_name="players")
    op.drop_table("players")
    op.drop_index("ix_teams_name", table_name="teams")
    op.drop_table("teams")
