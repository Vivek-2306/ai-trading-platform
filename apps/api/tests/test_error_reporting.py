"""Sentry is opt-in: off without a DSN."""

from unittest.mock import patch

from app.core.config import Settings
from app.core.error_reporting import init_error_reporting


def test_off_without_dsn() -> None:
    with patch("app.core.error_reporting.sentry_sdk.init") as init:
        assert init_error_reporting(Settings(_env_file=None)) is False
    init.assert_not_called()


def test_on_with_dsn() -> None:
    settings = Settings(_env_file=None, sentry_dsn="https://key@example.ingest.sentry.io/1")
    with patch("app.core.error_reporting.sentry_sdk.init") as init:
        assert init_error_reporting(settings) is True
    assert init.call_args.kwargs["dsn"] == settings.sentry_dsn
    assert init.call_args.kwargs["traces_sample_rate"] == 0.0
