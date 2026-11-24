"""Optional Sentry error reporting. Does nothing unless SENTRY_DSN is set."""

import sentry_sdk

from app.core.config import Settings


def init_error_reporting(settings: Settings) -> bool:
    """Start Sentry if configured; returns whether it is on."""
    if not settings.sentry_dsn:
        return False
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        release=settings.git_sha,
        traces_sample_rate=0.0,
    )
    return True
