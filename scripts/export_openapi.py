"""Export OpenAPI schema from FastAPI backend to frontend/openapi.json."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Add backend to sys.path
backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.main import app  # noqa: E402


def export_openapi() -> None:
    schema = app.openapi()
    output_path = Path(__file__).resolve().parent.parent / "frontend" / "openapi.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)
    print(f"Exported OpenAPI schema to {output_path}")


if __name__ == "__main__":
    export_openapi()
