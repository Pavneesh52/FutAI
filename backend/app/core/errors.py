"""Application error hierarchy.

Routers raise these; `app.main` maps them to HTTP status codes so no handler ever
has to build an error response by hand. Keeping the status code on the exception
means a new error type cannot be added without deciding how it surfaces.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base class for every error the app raises deliberately."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str = "", *, context: dict[str, Any] | None = None) -> None:
        self.message = message or self.__class__.__name__
        self.context: dict[str, Any] = dict(context or {})
        super().__init__(self.message)


class MatchNotFoundError(AppError):
    """The requested match does not exist in the data store."""

    status_code = 404
    code = "match_not_found"


class PlayerNotFoundError(AppError):
    """The requested player does not exist, or is not part of the match."""

    status_code = 404
    code = "player_not_found"


class DataUnavailableError(AppError):
    """The data source could not be reached or had no usable data for this request."""

    status_code = 502
    code = "data_unavailable"


class ToolExecutionError(AppError):
    """A deterministic tool failed. Carries the tool name in `context`."""

    status_code = 502
    code = "tool_execution_error"


class LLMError(AppError):
    """The LLM provider returned an error we cannot recover from."""

    status_code = 502
    code = "llm_error"


class LLMTimeoutError(AppError):
    """The LLM call exceeded `LLM_TIMEOUT_SECONDS` (rule R4)."""

    status_code = 504
    code = "llm_timeout"


class ValidationFailedError(AppError):
    """Model or agent output failed Pydantic validation (rule R3)."""

    status_code = 422
    code = "validation_failed"
