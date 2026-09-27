"""FastAPI application factory and process-level wiring.

`create_app` takes an optional `Settings` so tests can build an app with a known
configuration, and `app` at the bottom is what `uvicorn app.main:app` serves.

Windows: psycopg's async driver needs a selector event loop. Uvicorn picks its own loop
before importing this module, so the policy set in `app.core.eventloop` cannot reach it;
run uvicorn with
`--loop app.core.eventloop:psycopg_safe_uvicorn_loop_factory` (see the README).
"""

from __future__ import annotations

import asyncio
import sys

# Force Windows SelectorEventLoopPolicy before anything creates an event loop or connects to psycopg
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint

from app import __version__
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.db import dispose_engine
from app.core.errors import AppError
from app.core.eventloop import use_psycopg_compatible_event_loop
from app.core.logging import (
    REQUEST_ID_HEADER,
    configure_logging,
    get_logger,
    get_request_id,
    reset_request_id,
    set_request_id,
)

use_psycopg_compatible_event_loop()

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Log startup/shutdown and release pooled database connections."""
    logger.info("application_started")
    yield
    await dispose_engine()
    logger.info("application_stopped")


def _error_body(code: str, message: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build the single error envelope every failing request returns."""
    error: dict[str, Any] = {"code": code, "message": message}
    if context:
        error["context"] = context
    request_id = get_request_id()
    if request_id is not None:
        error["request_id"] = request_id
    return {"error": error}


def _register_request_id_middleware(app: FastAPI) -> None:
    """Attach a request id to every request/response and to the logging context."""

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        token = set_request_id(request_id)
        try:
            response = await call_next(request)
        finally:
            reset_request_id(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def _register_error_handlers(app: FastAPI) -> None:
    """Map the `AppError` hierarchy (and validation errors) onto HTTP responses."""

    async def handle_app_error(request: Request, exc: Exception) -> Response:
        if not isinstance(exc, AppError):  # pragma: no cover - defensive
            logger.error("non_app_error_reached_app_error_handler")
            return JSONResponse(
                status_code=500, content=_error_body("internal_error", "Unexpected server error.")
            )
        logger.warning("request_failed code=%s status=%d", exc.code, exc.status_code)
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code, exc.message, exc.context),
        )

    async def handle_validation_error(request: Request, exc: Exception) -> Response:
        details: list[dict[str, Any]] = []
        if isinstance(exc, RequestValidationError):
            details = [
                {
                    "loc": [str(part) for part in error.get("loc", ())],
                    "msg": str(error.get("msg", "")),
                }
                for error in exc.errors()
            ]
        return JSONResponse(
            status_code=422,
            content=_error_body(
                "validation_failed", "Request validation failed.", {"errors": details}
            ),
        )

    async def handle_unexpected_error(request: Request, exc: Exception) -> Response:
        # Log the traceback for debugging, but never leak it to the client.
        logger.exception("unhandled_exception")
        return JSONResponse(
            status_code=500, content=_error_body("internal_error", "Unexpected server error.")
        )

    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(Exception, handle_unexpected_error)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application."""
    resolved = settings or get_settings()
    configure_logging(resolved)

    app = FastAPI(
        title="AI Football Match Analyst",
        version=__version__,
        summary="Ask questions about a football match; every number traces to a tool call.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],
    )

    _register_request_id_middleware(app)
    _register_error_handlers(app)
    app.include_router(api_router)

    return app


app = create_app()
