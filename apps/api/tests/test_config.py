"""Tests for settings loading."""

from pathlib import Path

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


def test_repo_root_found_in_monorepo() -> None:
    from app.core.config import REPO_ROOT

    assert REPO_ROOT is not None
    assert (REPO_ROOT / "pnpm-workspace.yaml").is_file()


def test_repo_root_is_none_outside_monorepo(tmp_path: Path) -> None:
    from app.core.config import _find_repo_root

    nested = tmp_path / "app" / "app" / "core" / "config.py"
    assert _find_repo_root(nested) is None


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    # Don't read the developer's real env file.
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()
    try:
        assert get_settings() is get_settings()
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize("origins", ["*", "http://localhost:3000,*"])
def test_rejects_wildcard_cors_origin(monkeypatch: pytest.MonkeyPatch, origins: str) -> None:
    monkeypatch.setenv("CORS_ORIGINS", origins)

    with pytest.raises(ValidationError, match="not allowed"):
        Settings(_env_file=None)


def test_ai_settings_defaults_and_secrets_are_hidden() -> None:
    settings = Settings(_env_file=None, anthropic_api_key="sk-ant-secret")

    assert settings.ai_model_bulk == "claude-haiku-5-5"
    assert settings.ai_model_reasoning == "claude-opus-5-5"
    assert settings.voyage_api_key is None
    assert "sk-ant-secret" not in repr(settings)
    assert settings.anthropic_api_key is not None
    assert settings.anthropic_api_key.get_secret_value() == "sk-ant-secret"
