"""Tests for log output format per environment."""

import json

import pytest

from app.core.config import Settings
from app.core.logging import configure_logging, get_logger


def test_production_logs_are_json(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(Settings(_env_file=None, app_env="production"))

    get_logger("test").info("order_checked", symbol="NIFTY", qty=1)

    line = capsys.readouterr().out.strip().splitlines()[-1]
    record = json.loads(line)
    assert record["event"] == "order_checked"
    assert record["symbol"] == "NIFTY"
    assert record["level"] == "info"
    assert record["timestamp"].endswith("Z")


def test_development_logs_are_readable_text(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(Settings(_env_file=None, app_env="development"))

    get_logger("test").info("hello_dev")

    out = capsys.readouterr().out
    assert "hello_dev" in out
    with pytest.raises(json.JSONDecodeError):
        json.loads(out.strip().splitlines()[-1])


def test_log_level_filters_lower_levels(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(Settings(_env_file=None, app_env="production", log_level="warning"))

    log = get_logger("test")
    log.info("hidden")
    log.warning("shown")

    out = capsys.readouterr().out
    assert "hidden" not in out
    assert "shown" in out
