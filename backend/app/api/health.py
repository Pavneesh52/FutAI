"""Health endpoint.

Kept dependency-light on purpose: it is the endpoint CI, the frontend and (from
Phase 12b) the hosting platform's health check all poll.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.core.db import check_database
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness check plus dependency status",
)
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    """Report whether the API is up, and whether its database is reachable.

    Always returns HTTP 200 while the process is serving: a database that is down or
    not yet configured is reported in the body (rule R5 -- degrade, don't crash).
    """
    db = await check_database(settings)
    return HealthResponse(status="degraded" if db == "unavailable" else "ok", db=db)
