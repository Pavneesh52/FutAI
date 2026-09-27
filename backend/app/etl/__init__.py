"""ETL: turn a source's raw feed into normalised database rows.

Lives inside `app/` (not in `scripts/`) so the parsing logic is importable and unit
testable; `scripts/*.py` are thin CLI wrappers around it.
"""
