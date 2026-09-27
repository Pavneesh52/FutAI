#!/usr/bin/env python
"""Take a fresh clone to a usable app: migrate the database, then load the dataset.

    docker compose up -d
    uv run --project backend python scripts/seed.py

Idempotent: `alembic upgrade head` on an up-to-date database is a no-op, and the ETL
upserts by provider id. Phase 2 extends this with `scripts/compute_stats.py`.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.etl.statsbomb import main as etl_main  # noqa: E402
from scripts.compute_stats import run as compute_stats_run  # noqa: E402

#: The dataset chosen in docs/data-source.md.
DEFAULT_COMPETITION_ID = 223  # Copa America
DEFAULT_SEASON_ID = 282  # 2024


def build_parser() -> argparse.ArgumentParser:
    """CLI definition."""
    parser = argparse.ArgumentParser(description="Migrate the database and seed the dataset.")
    parser.add_argument("--competition-id", type=int, default=DEFAULT_COMPETITION_ID)
    parser.add_argument("--season-id", type=int, default=DEFAULT_SEASON_ID)
    parser.add_argument("--skip-migrate", action="store_true", help="Do not run Alembic")
    parser.add_argument("--skip-etl", action="store_true", help="Do not load match data")
    parser.add_argument("--skip-stats", action="store_true", help="Do not compute match statistics")
    parser.add_argument("--refresh", action="store_true", help="Re-download cached raw files")
    parser.add_argument("--offline", action="store_true", help="Never download")
    return parser


def migrate() -> None:
    """Run `alembic upgrade head` against the configured database."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(config, "head")


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
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

    if not args.skip_migrate:
        print("Applying migrations...")
        migrate()

    if not args.skip_etl:
        etl_argv = [
            "--competition-id",
            str(args.competition_id),
            "--season-id",
            str(args.season_id),
        ]
        if args.refresh:
            etl_argv.append("--refresh")
        if args.offline:
            etl_argv.append("--offline")

        code = etl_main(etl_argv)
        if code != 0:
            return code
    else:
        print("Skipping the ETL (--skip-etl).")

    if not args.skip_stats:
        print("Computing advanced match statistics...")
        import asyncio
        code = asyncio.run(compute_stats_run(None, settings))
        if code != 0:
            return code
    else:
        print("Skipping statistics computation (--skip-stats).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
