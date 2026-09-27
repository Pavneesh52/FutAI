"""Health response model. Contract: IMPLEMENTATION.md section 6.4 (`{status, db}`)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.core.db import DatabaseStatus


class HealthResponse(BaseModel):
    """Result of `GET /health`."""

    status: Literal["ok", "degraded"] = Field(
        description=(
            "`degraded` when a required dependency is unreachable; the process is still serving."
        ),
    )
    db: DatabaseStatus = Field(
        description="Database probe result: `ok`, `unavailable`, or `not_configured`.",
    )
