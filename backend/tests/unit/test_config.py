"""Tests for `app.core.config`."""

from __future__ import annotations

import pytest
from app.core.config import get_settings
from pydantic import ValidationError

from tests.conftest import offline_settings


def test_defaults_suit_a_fresh_local_checkout() -> None:
    settings = offline_settings()

    assert settings.environment == "local"
    assert settings.database_url == ""
    assert settings.llm_timeout_seconds == 45.0
    assert settings.max_critic_retries == 2
    assert settings.cors_origins_list == ["http://localhost:5173"]


def test_cors_origins_are_split_and_trimmed() -> None:
    settings = offline_settings(cors_origins="http://localhost:5173, https://app.example.com ,")

    assert settings.cors_origins_list == ["http://localhost:5173", "https://app.example.com"]


def test_cors_origins_defaults_when_blank() -> None:
    assert offline_settings(cors_origins="   ").cors_origins_list == []


def test_invalid_environment_is_rejected() -> None:
    with pytest.raises(ValidationError):
        offline_settings(environment="banana")


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()
