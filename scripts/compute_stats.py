#!/usr/bin/env python
"""Compute advanced analytics and update team_match_stats (Phase 2).

    uv run --project backend python scripts/compute_stats.py
    uv run --project backend python scripts/compute_stats.py --match-id 42

Idempotent: re-running updates existing rows rather than creating duplicates.
Reads events from the database, computes possession_pct / ppda / field_tilt via the
pure analytics functions, and writes the results back.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.analytics.metrics import field_tilt, possession_pct, ppda  # noqa: E402
from app.analytics.types import EventRecord  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.db import session_scope  # noqa: E402
from app.core.eventloop import use_psycopg_compatible_event_loop  # noqa: E402
from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.models import Event, Match, TeamMatchStats  # noqa: E402
from sqlalchemy import select, update  # noqa: E402

use_psycopg_compatible_event_loop()
configure_logging(get_settings())
logger = get_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """CLI definition."""
    parser = argparse.ArgumentParser(description="Compute advanced match statistics.")
    parser.add_argument(
        "--match-id",
        type=int,
        default=None,
        help="Compute stats for a single match (default: all matches).",
    )
    return parser


def _events_to_records(
    rows: Sequence[Event],
) -> list[EventRecord]:
    """Convert ORM Event rows to analytics EventRecord objects."""
    return [
        EventRecord(
            event_type=row.event_type,
            team_id=row.team_id,
            player_id=row.player_id,
            x=row.x,
            y=row.y,
            outcome=row.outcome,
            xg=row.xg,
            possession_id=row.possession_id,
            minute=row.minute,
            second=row.second,
        )
        for row in rows
    ]


async def compute_match(match_id: int, settings: object) -> bool:
    """Compute and update stats for one match. Returns True if rows were updated."""
    async with session_scope(settings) as session:  # type: ignore[arg-type]
        # Fetch the two teams for this match.
        match_row = (
            await session.execute(select(Match).where(Match.id == match_id))
        ).scalar_one_or_none()
        if match_row is None:
            logger.warning("match_not_found: match_id=%s", match_id)
            return False

        team_ids = [match_row.home_team_id, match_row.away_team_id]

        # Fetch all events for this match.
        event_rows = (
            await session.execute(
                select(Event)
                .where(Event.match_id == match_id)
                .order_by(Event.minute, Event.second, Event.id)
            )
        ).scalars().all()

        if not event_rows:
            logger.info("no_events: match_id=%s", match_id)
            return False

        records = _events_to_records(event_rows)

        updated = 0
        for team_id in team_ids:
            poss = possession_pct(records, team_id)
            ppda_val = ppda(records, team_id, all_team_ids=team_ids)
            ft = field_tilt(records, team_id)

            result = await session.execute(
                update(TeamMatchStats)
                .where(
                    TeamMatchStats.match_id == match_id,
                    TeamMatchStats.team_id == team_id,
                )
                .values(
                    possession_pct=poss,
                    ppda=ppda_val,
                    field_tilt=ft,
                )
            )
            updated += result.rowcount  # type: ignore[operator]

        await session.commit()

        if updated > 0:
            logger.info(
                "match_stats_updated: match_id=%s rows_updated=%d",
                match_id,
                updated,
            )
        return updated > 0


async def run(match_id: int | None, settings: object) -> int:
    """Compute stats for one or all matches. Returns exit code."""
    async with session_scope(settings) as session:  # type: ignore[arg-type]
        if match_id is not None:
            match_ids = [match_id]
        else:
            rows = (await session.execute(select(Match.id).order_by(Match.id))).scalars().all()
            match_ids = list(rows)

    total = len(match_ids)
    computed = 0
    for mid in match_ids:
        if await compute_match(mid, settings):
            computed += 1

    logger.info("compute_stats_done: total_matches=%d updated=%d", total, computed)
    print(f"Done: {computed}/{total} matches updated.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point."""
    args = build_parser().parse_args(argv)
    settings = get_settings()

    if not settings.database_url:
        print(
            "DATABASE_URL is not set.\n"
            "Copy .env.example to .env at the repository root, then start Postgres with "
            "`docker compose up -d`.",
            file=sys.stderr,
        )
        return 1

    return asyncio.run(run(args.match_id, settings))


if __name__ == "__main__":
    raise SystemExit(main())
