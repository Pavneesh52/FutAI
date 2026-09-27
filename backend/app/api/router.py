"""FastAPI router aggregation.

Routers live in their own modules and are mounted here, so `app.main` only ever
imports one router object.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.analysis import router as analysis_router
from app.api.health import router as health_router
from app.api.matches import router as matches_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(matches_router)
api_router.include_router(analysis_router)
