"""Structured JSON logging.

Every log line is a single JSON object carrying a `request_id` (and, from Phase 5, an
`agent_run_id`) so one request can be followed across routers, tools and agents.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings

REQUEST_ID_HEADER = "X-Request-ID"

_environment: str = "local"
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_agent_run_id: ContextVar[str | None] = ContextVar("agent_run_id", default=None)


class JsonFormatter(logging.Formatter):
    """Renders each log record as one line of JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "environment": _environment,
        }

        request_id = _request_id.get()
        if request_id is not None:
            payload["request_id"] = request_id

        agent_run_id = _agent_run_id.get()
        if agent_run_id is not None:
            payload["agent_run_id"] = agent_run_id

        if record.exc_info is not None:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def configure_logging(settings: Settings) -> None:
    """Install the JSON formatter on the root logger and on uvicorn's loggers."""
    global _environment
    _environment = settings.environment

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())

    # uvicorn installs its own handlers, which would emit non-JSON lines.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.addHandler(handler)
        uvicorn_logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Return a named logger (use `__name__`)."""
    return logging.getLogger(name)


def get_request_id() -> str | None:
    """Return the request id bound to the current context, if any."""
    return _request_id.get()


def set_request_id(request_id: str) -> Token[str | None]:
    """Bind a request id to the current context. Returns a token for `reset_request_id`."""
    return _request_id.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    """Restore the previous request id."""
    _request_id.reset(token)


def set_agent_run_id(agent_run_id: str) -> Token[str | None]:
    """Bind an agent run id to the current context (wired up in Phase 5)."""
    return _agent_run_id.set(agent_run_id)


def reset_agent_run_id(token: Token[str | None]) -> None:
    """Restore the previous agent run id."""
    _agent_run_id.reset(token)
