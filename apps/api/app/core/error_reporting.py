"""Optional Sentry error reporting. Does nothing unless SENTRY_DSN is set."""

from typing import Any

import sentry_sdk

from app.core.config import Settings
from app.core.logging import redact_value


def _scrub(event: Any, _hint: Any) -> Any:
    """Apply the same redaction as our logs to everything sent to Sentry."""
    return redact_value(event)


def init_error_reporting(settings: Settings) -> bool:
    """Start Sentry if configured; returns whether it is on."""
    if not settings.sentry_dsn:
        return False
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        release=settings.git_sha,
        traces_sample_rate=0.0,
        max_request_body_size="never",
        before_send=_scrub,
        before_breadcrumb=_scrub,
    )
    return True
