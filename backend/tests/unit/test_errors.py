"""Tests for the `AppError` hierarchy (IMPLEMENTATION.md section 4)."""

from __future__ import annotations

import pytest
from app.core.errors import (
    AppError,
    DataUnavailableError,
    LLMError,
    LLMTimeoutError,
    MatchNotFoundError,
    PlayerNotFoundError,
    ToolExecutionError,
    ValidationFailedError,
)


@pytest.mark.parametrize(
    ("error_class", "status_code", "code"),
    [
        (MatchNotFoundError, 404, "match_not_found"),
        (PlayerNotFoundError, 404, "player_not_found"),
        (DataUnavailableError, 502, "data_unavailable"),
        (ToolExecutionError, 502, "tool_execution_error"),
        (LLMError, 502, "llm_error"),
        (LLMTimeoutError, 504, "llm_timeout"),
        (ValidationFailedError, 422, "validation_failed"),
    ],
)
def test_every_error_declares_its_http_status(
    error_class: type[AppError], status_code: int, code: str
) -> None:
    """A new error type cannot be added without deciding how it surfaces."""
    error = error_class()

    assert isinstance(error, AppError)
    assert isinstance(error, Exception)
    assert error.status_code == status_code
    assert error.code == code


def test_message_defaults_to_the_class_name() -> None:
    assert MatchNotFoundError().message == "MatchNotFoundError"


def test_context_is_copied_not_aliased() -> None:
    context = {"match_id": 42}
    error = MatchNotFoundError("gone", context=context)

    context["match_id"] = 99

    assert error.context == {"match_id": 42}
    assert error.context is not context


def test_str_returns_the_message() -> None:
    assert str(LLMTimeoutError("model took too long")) == "model took too long"
