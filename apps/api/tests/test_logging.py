"""Tests for log output format per environment."""

import json
import logging
from pathlib import Path

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


def test_stdlib_and_uvicorn_logs_are_json_in_production(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(Settings(_env_file=None, app_env="production"))

    logging.getLogger("uvicorn.error").warning("server_started")

    record = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert record["event"] == "server_started"
    assert record["level"] == "warning"
    assert record["logger"] == "uvicorn.error"


def test_uvicorn_access_log_is_silenced(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(Settings(_env_file=None, app_env="production"))

    logging.getLogger("uvicorn.access").warning("GET /health 200")

    captured = capsys.readouterr()
    assert "GET /health" not in captured.out + captured.err


def test_secret_fields_are_redacted_at_any_depth(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(Settings(_env_file=None, app_env="production"))

    get_logger("test").info(
        "login", password="hunter2", user={"name": "a", "API_Key": "k-123"}, path="/x"
    )

    out = capsys.readouterr().out
    assert "hunter2" not in out
    assert "k-123" not in out
    record = json.loads(out.strip().splitlines()[-1])
    assert record["password"] == "[redacted]"
    assert record["user"] == {"name": "a", "API_Key": "[redacted]"}
    assert record["path"] == "/x"


def test_log_file_gets_json_lines_when_configured(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    log_file = tmp_path / "logs" / "api.log"
    configure_logging(Settings(_env_file=None, app_env="development", log_file=str(log_file)))

    get_logger("test").info("to_file", token="abc", n=1)
    logging.getLogger("uvicorn.error").warning("from_stdlib")
    capsys.readouterr()

    lines = [json.loads(line) for line in log_file.read_text().splitlines()]
    events = {line["event"]: line for line in lines}
    assert events["to_file"]["n"] == 1
    assert events["to_file"]["token"] == "[redacted]"
    assert "from_stdlib" in events


def test_no_log_file_by_default(tmp_path: Path) -> None:
    configure_logging(Settings(_env_file=None))

    assert not logging.getLogger("aitp.logfile").handlers
