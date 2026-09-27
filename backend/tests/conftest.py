"""Shared test fixtures and helpers."""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.core.eventloop import use_psycopg_compatible_event_loop
from app.main import create_app
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

# Runs at import, which is before pytest-asyncio creates any loop: psycopg's async
# driver cannot use Windows' default ProactorEventLoop.
use_psycopg_compatible_event_loop()


def build_app(settings: Settings) -> FastAPI:
    """Build an app for testing that resolves `Settings` from the override, not the env.

    Tests must never depend on the developer's real `.env`, so we always inject an
    explicit `Settings` instance here.
    """
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    return app


def build_client(app: FastAPI) -> AsyncClient:
    """Return an AsyncClient bound to the app over ASGI (no network, no server)."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


def offline_settings(**overrides: object) -> Settings:
    """Settings with env-file loading disabled, so tests are hermetic."""
    return Settings(_env_file=None, **overrides)  # type: ignore[arg-type]
