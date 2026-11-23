"""Celery application.

Run from apps/api (needs Redis: `pnpm infra:up`):
    uv run celery -A app.worker.celery_app worker --loglevel=info
    uv run celery -A app.worker.celery_app beat --loglevel=info
"""

from typing import Any

from celery import Celery
from celery.signals import setup_logging

from app.core.config import Settings, get_settings
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
        task_acks_late=True,  # a crashed worker's task is redelivered, not lost
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,  # long analysis jobs: take one at a time
        result_expires=24 * 3600,
        broker_connection_retry_on_startup=True,
        worker_hijack_root_logger=False,  # keep our structlog setup
        beat_schedule={
            "heartbeat": {
                "task": "app.worker.tasks.heartbeat",
                "schedule": settings.heartbeat_interval_seconds,
            },
        },
    )
    return app


@setup_logging.connect
def _use_structlog(**_: Any) -> None:
    """Route Celery's logging through our structlog configuration."""
    configure_logging(get_settings())


celery_app = create_celery(get_settings())
