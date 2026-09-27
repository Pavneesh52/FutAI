"""Tests for GET /health plus the error-handling wiring (Phase 0 acceptance checks)."""

from __future__ import annotations

import pytest
from app.api import health as health_module
from app.core.config import Settings
from app.core.db import DatabaseStatus
from app.core.errors import MatchNotFoundError
from app.core.logging import REQUEST_ID_HEADER

from tests.conftest import build_app, build_client, offline_settings


async def test_health_returns_200_with_documented_shape() -> None:
    """Acceptance check: `GET /health` returns 200 and `{status, db}`."""
    settings = offline_settings(database_url="")
    async with build_client(build_app(settings)) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "not_configured"}


async def test_health_is_ok_when_database_is_reachable(monkeypatch: pytest.MonkeyPatch) -> None:
    """A reachable database keeps the service `ok`."""
    _stub_probe(monkeypatch, "ok")
    async with build_client(build_app(offline_settings(database_url=""))) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}


async def test_health_degrades_instead_of_failing_when_database_is_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rule R5: an unreachable dependency produces a degraded body, not a 5xx."""
    _stub_probe(monkeypatch, "unavailable")
    async with build_client(build_app(offline_settings(database_url=""))) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "degraded", "db": "unavailable"}


async def test_health_returns_a_request_id_header() -> None:
    async with build_client(build_app(offline_settings(database_url=""))) as client:
        response = await client.get("/health")

    assert response.headers[REQUEST_ID_HEADER]


async def test_health_echoes_a_caller_supplied_request_id() -> None:
    app = build_app(offline_settings(database_url=""))
    async with build_client(app) as client:
        response = await client.get("/health", headers={REQUEST_ID_HEADER: "trace-me-123"})

    assert response.headers[REQUEST_ID_HEADER] == "trace-me-123"


async def test_app_error_maps_to_its_http_status_and_envelope() -> None:
    """Routers raise `AppError` subclasses; the app converts them to HTTP responses."""
    app = build_app(offline_settings(database_url=""))

    @app.get("/boom")
    async def boom() -> None:
        raise MatchNotFoundError("no such match", context={"match_id": 42})

    async with build_client(app) as client:
        response = await client.get("/boom")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "match_not_found"
    assert error["message"] == "no such match"
    assert error["context"] == {"match_id": 42}
    assert error["request_id"]


async def test_malformed_query_parameters_return_the_validation_envelope() -> None:
    """Rule R3: malformed input fails fast, in the same envelope as other errors."""
    app = build_app(offline_settings(database_url=""))

    @app.get("/needs-int")
    async def needs_int(value: int) -> dict[str, int]:
        return {"value": value}

    async with build_client(app) as client:
        response = await client.get("/needs-int", params={"value": "not-an-int"})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_failed"
    assert error["context"]["errors"][0]["loc"] == ["query", "value"]


def _stub_probe(monkeypatch: pytest.MonkeyPatch, status: DatabaseStatus) -> None:
    """Replace the database probe so status mapping is tested without a database."""

    async def probe(settings: Settings) -> DatabaseStatus:
        return status

    monkeypatch.setattr(health_module, "check_database", probe)
