"""Celery application.

Run from apps/api (needs Redis: `pnpm infra:up`):
    uv run celery -A app.worker.celery_app worker --loglevel=info
    uv run celery -A app.worker.celery_app beat --loglevel=info
"""

from typing import Any

from celery import Celery
from celery.schedules import crontab
from celery.signals import setup_logging

from app.core.config import Settings, get_settings
from app.core.error_reporting import init_error_reporting
from app.core.logging import configure_logging


def create_celery(settings: Settings) -> Celery:
    app = Celery(
        "aitp",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
        include=["app.worker.tasks"],
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        # Acknowledge after the task finishes, so a worker that is stopped mid-task hands
        # the task back instead of losing it. Tasks must therefore be safe to run twice.
        task_acks_late=True,
        # A task that kills its worker (e.g. out of memory) is NOT redelivered: with
        # acks_late it would otherwise crash workers in a loop. (Celery's default.)
        task_reject_on_worker_lost=False,
        # Redis redelivers an unacknowledged task after this many seconds. It must exceed
        # the longest task (backtests, training), or that task runs twice in parallel.
        broker_transport_options={"visibility_timeout": settings.task_visibility_timeout_seconds},
        worker_prefetch_multiplier=1,  # long analysis jobs: take one at a time
        result_expires=24 * 3600,
        broker_connection_retry_on_startup=True,
        worker_hijack_root_logger=False,  # keep our structlog setup
        worker_redirect_stdouts=False,  # else structlog's stdout lines would be logged twice
        beat_schedule={
            "heartbeat": {
                "task": "app.worker.tasks.heartbeat",
                "schedule": settings.heartbeat_interval_seconds,
            },
            "candle-retention": {
                "task": "app.worker.tasks.apply_candle_retention",
                "schedule": crontab(hour=3, minute=30),
            },
            # Two minutes past each hour, once the exchange has published the closed candle.
            # Ten minutes past each hour: after the candle update has finished.
            "run-signals": {
                "task": "app.worker.tasks.run_signals",
                "schedule": crontab(minute=10),
            },
            "update-candles": {
                "task": "app.worker.tasks.update_candles",
                "schedule": crontab(minute=2),
            },
        },
    )
    return app


@setup_logging.connect
def _use_structlog(**_: Any) -> None:
    """Route Celery's logging through our structlog configuration."""
    configure_logging(get_settings())
    init_error_reporting(get_settings())


celery_app = create_celery(get_settings())
