"""Background tasks. Real jobs (data pulls, analysis, backtests) arrive in feature phases."""

from datetime import UTC, datetime

from app.core.logging import get_logger
from app.worker.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="app.worker.tasks.ping")
def ping() -> str:
    """Round-trip check: a worker is consuming the queue."""
    return "pong"


@celery_app.task(name="app.worker.tasks.heartbeat")
def heartbeat() -> str:
    """Scheduled by beat; proves beat and a worker are both alive. Logs only."""
    now = datetime.now(UTC).isoformat()
    logger.info("worker_heartbeat", at=now)
    return now
