"""Tests for settings loading."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_defaults_are_safe() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_env == "development"
    assert settings.trading_mode == "paper"
    assert settings.is_production is False


def test_reads_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("API_PORT", "9000")
    monkeypatch.setenv("GIT_SHA", "deadbee")

    settings = Settings(_env_file=None)

    assert settings.is_production is True
    assert settings.api_port == 9000
    assert settings.git_sha == "deadbee"


def test_cors_origins_accept_comma_separated_string(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000, https://app.example.com")

    settings = Settings(_env_file=None)

    assert settings.cors_origins == ["http://localhost:3000", "https://app.example.com"]


def test_rejects_unknown_trading_mode() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, trading_mode="yolo")


def test_get_settings_is_cached() -> None:
    from app.core.config import get_settings

    assert get_settings() is get_settings()
