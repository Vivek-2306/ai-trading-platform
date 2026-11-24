"""Tests for the Celery app and tasks (run in-process; no broker needed)."""

from structlog.testing import capture_logs

from app.core.config import Settings, get_settings
from app.worker.celery_app import celery_app, create_celery
from app.worker.tasks import heartbeat, ping


def test_ping_returns_pong() -> None:
    assert ping.apply().get() == "pong"


def test_heartbeat_logs_and_returns_timestamp() -> None:
    with capture_logs() as logs:
        result = heartbeat.apply().get()

    assert result.endswith("+00:00")
    assert any(log["event"] == "worker_heartbeat" for log in logs)


def test_beat_schedules_heartbeat() -> None:
    entry = celery_app.conf.beat_schedule["heartbeat"]

    assert entry["task"] == "app.worker.tasks.heartbeat"
    assert entry["schedule"] == get_settings().heartbeat_interval_seconds


def test_celery_uses_configured_urls_and_json_only() -> None:
    app = create_celery(
        Settings(
            _env_file=None,
            celery_broker_url="redis://broker.example:6379/1",
            celery_result_backend="redis://broker.example:6379/2",
        )
    )

    assert app.conf.broker_url == "redis://broker.example:6379/1"
    assert app.conf.result_backend == "redis://broker.example:6379/2"
    assert app.conf.accept_content == ["json"]
    assert app.conf.task_acks_late is True
    assert app.conf.task_reject_on_worker_lost is False
    assert app.conf.broker_transport_options == {"visibility_timeout": 6 * 3600}


def test_tasks_are_registered() -> None:
    celery_app.loader.import_default_modules()

    assert "app.worker.tasks.ping" in celery_app.tasks
    assert "app.worker.tasks.heartbeat" in celery_app.tasks


def test_heartbeat_result_is_not_stored() -> None:
    assert heartbeat.ignore_result is True


def test_beat_schedules_the_candle_update_hourly() -> None:
    entry = celery_app.conf.beat_schedule["update-candles"]

    assert entry["task"] == "app.worker.tasks.update_candles"
    assert entry["schedule"].minute == {2}


def test_beat_schedules_daily_candle_retention() -> None:
    entry = celery_app.conf.beat_schedule["candle-retention"]

    assert entry["task"] == "app.worker.tasks.apply_candle_retention"
    assert entry["schedule"].hour == {3}


def test_retention_defaults_to_90_days_and_zero_keeps_everything() -> None:
    assert Settings(_env_file=None).candle_1m_retention_days == 90
    assert Settings(_env_file=None, candle_1m_retention_days=0).candle_1m_retention_days == 0


def test_beat_runs_signals_after_the_candle_update() -> None:
    update = celery_app.conf.beat_schedule["update-candles"]["schedule"]
    signals = celery_app.conf.beat_schedule["run-signals"]

    assert signals["task"] == "app.worker.tasks.run_signals"
    assert min(signals["schedule"].minute) > max(update.minute)
