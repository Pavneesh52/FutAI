"""Tests for structured JSON logging."""

from __future__ import annotations

import json
import logging

from app.core.logging import (
    JsonFormatter,
    configure_logging,
    get_logger,
    get_request_id,
    reset_agent_run_id,
    reset_request_id,
    set_agent_run_id,
    set_request_id,
)

from tests.conftest import offline_settings


def _record(message: str = "hello %s", *args: object) -> logging.LogRecord:
    return logging.LogRecord(
        name="tests",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=args,
        exc_info=None,
    )


def test_every_line_is_json_with_a_message_and_environment() -> None:
    configure_logging(offline_settings(environment="test"))

    payload = json.loads(JsonFormatter().format(_record("hello %s", "world")))

    assert payload["message"] == "hello world"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "tests"
    assert payload["environment"] == "test"
    assert "timestamp" in payload


def test_request_id_is_attached_while_bound_and_absent_after_reset() -> None:
    formatter = JsonFormatter()
    token = set_request_id("req-1")
    try:
        assert json.loads(formatter.format(_record()))["request_id"] == "req-1"
        assert get_request_id() == "req-1"
    finally:
        reset_request_id(token)

    assert "request_id" not in json.loads(formatter.format(_record()))


def test_agent_run_id_is_attached_while_bound() -> None:
    formatter = JsonFormatter()
    token = set_agent_run_id("run-9")
    try:
        assert json.loads(formatter.format(_record()))["agent_run_id"] == "run-9"
    finally:
        reset_agent_run_id(token)


def test_exceptions_are_serialized_into_the_payload() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord(
            name="tests",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="failed",
            args=(),
            exc_info=__import__("sys").exc_info(),
        )

    payload = json.loads(JsonFormatter().format(record))

    assert "ValueError: boom" in payload["exception"]


def test_configure_logging_installs_the_json_formatter() -> None:
    configure_logging(offline_settings(log_level="WARNING"))

    root = logging.getLogger()

    assert root.level == logging.WARNING
    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0].formatter, JsonFormatter)
    assert get_logger("whatever").name == "whatever"
