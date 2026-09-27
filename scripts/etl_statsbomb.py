#!/usr/bin/env python
"""Thin CLI wrapper around `app.etl.statsbomb`.

Run from the repository root:

    uv run --project backend python scripts/etl_statsbomb.py --competition-id 223 --season-id 282

Cached raw JSON lands in `data/raw/statsbomb/` (gitignored), so each re-run is offline and
fast. The load itself is idempotent: re-running never duplicates rows.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.etl.statsbomb import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
