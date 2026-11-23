"""Tests for the Celery app and tasks (run in-process; no broker needed)."""

from structlog.testing import capture_logs

from app.core.config import Settings
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
    assert entry["schedule"] == 60


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


def test_tasks_are_registered() -> None:
    celery_app.loader.import_default_modules()

    assert "app.worker.tasks.ping" in celery_app.tasks
    assert "app.worker.tasks.heartbeat" in celery_app.tasks
