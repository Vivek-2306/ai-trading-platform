"""Tests for log output format per environment."""

import json
import logging
import logging.handlers
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

    assert not any(
        isinstance(h, logging.handlers.RotatingFileHandler) for h in logging.getLogger().handlers
    )


def test_secrets_inside_text_and_tracebacks_are_redacted(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(Settings(_env_file=None, app_env="production"))
    log = get_logger("test")

    try:
        raise ValueError("cannot connect to postgres://user:pw123@db/app?token=abc999")
    except ValueError:
        log.exception("failed", note="Authorization: Bearer xyz789")

    out = capsys.readouterr().out
    for secret in ("pw123", "abc999", "xyz789"):
        assert secret not in out
    assert "postgres://user:" in out  # the rest of the message is kept


def test_stdlib_records_are_redacted(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(Settings(_env_file=None, app_env="production"))

    logging.getLogger("httpx").warning("GET https://api.example.com/x?api_key=sk-live-1 failed")

    assert "sk-live-1" not in capsys.readouterr().err


def test_key_matching_handles_hyphens_and_spares_token_counters(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(Settings(_env_file=None, app_env="production"))

    get_logger("test").info("usage", **{"x-api-key": "k1", "max_tokens": 100, "tokens_used": 7})

    record = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert record["x-api-key"] == "[redacted]"
    assert record["max_tokens"] == 100
    assert record["tokens_used"] == 7


def test_reconfiguring_does_not_stack_handlers_or_touch_foreign_ones(tmp_path: Path) -> None:
    root = logging.getLogger()
    foreign = logging.NullHandler()
    root.addHandler(foreign)
    settings = Settings(_env_file=None, log_file=str(tmp_path / "api.log"))
    try:
        configure_logging(settings)
        count = len(root.handlers)
        configure_logging(settings)
        configure_logging(settings)

        assert len(root.handlers) == count
        assert foreign in root.handlers

        get_logger("test").info("once")
        lines = (tmp_path / "api.log").read_text().splitlines()
        assert sum('"once"' in line for line in lines) == 1
    finally:
        root.removeHandler(foreign)


def test_exception_traceback_reaches_the_log_file(tmp_path: Path) -> None:
    configure_logging(Settings(_env_file=None, log_file=str(tmp_path / "api.log")))

    try:
        raise RuntimeError("boom")
    except RuntimeError:
        get_logger("test").exception("failed")

    assert "RuntimeError: boom" in (tmp_path / "api.log").read_text()
