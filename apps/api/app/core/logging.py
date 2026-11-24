"""Structured logging with structlog.

Production writes one JSON object per line (easy to ship to a log service); development
writes readable, coloured lines. Request-scoped values (request ID, method, path) are bound
with structlog's contextvars and appear on every log line for that request.
"""

import logging
import logging.handlers
from pathlib import Path
from typing import Any

import structlog

from app.core.config import Settings

_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}


REDACTED = "[redacted]"
# A key containing any of these (case-insensitive) has its value hidden.
_SENSITIVE_KEYS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
)
_FILE_LOGGER = "aitp.logfile"


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: REDACTED
            if isinstance(key, str) and any(part in key.lower() for part in _SENSITIVE_KEYS)
            else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [_redact(item) for item in value]
    return value


def redact_secrets(
    _logger: object, _method: str, event_dict: structlog.typing.EventDict
) -> structlog.typing.EventDict:
    """Hide the value of any field whose name looks like a secret, at any depth."""
    redacted: structlog.typing.EventDict = _redact(event_dict)
    return redacted


def _file_handler(path: str) -> logging.Handler:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return logging.handlers.RotatingFileHandler(
        path, maxBytes=10_000_000, backupCount=5, encoding="utf-8"
    )


def _write_to_file(
    _logger: object, _method: str, event_dict: structlog.typing.EventDict
) -> structlog.typing.EventDict:
    """Copy each structlog line, as JSON, to the rotating log file (when one is configured)."""
    line = structlog.processors.JSONRenderer()(_logger, _method, dict(event_dict))
    logging.getLogger(_FILE_LOGGER).info(line)
    return event_dict


def _close_handlers(logger: logging.Logger) -> None:
    """Remove and close handlers from an earlier configure call (releases log files)."""
    for old in list(logger.handlers):
        logger.removeHandler(old)
        old.close()


def configure_logging(settings: Settings) -> None:
    """Configure structlog for this process. Safe to call more than once.

    Standard-library loggers (uvicorn, libraries) are routed through the same renderer, so
    production output is JSON only. Uvicorn's access log is silenced: the request
    middleware already logs every request once, with its request ID.
    """
    level = _LEVELS[settings.log_level]
    renderer: structlog.typing.Processor = (
        structlog.processors.JSONRenderer()
        if settings.is_production
        else structlog.dev.ConsoleRenderer()
    )
    shared: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        redact_secrets,
    ]
    _close_handlers(logging.getLogger())
    file_logger = logging.getLogger(_FILE_LOGGER)
    _close_handlers(file_logger)
    file_logger.propagate = False
    file_processors: list[structlog.typing.Processor] = []
    if settings.log_file:
        handler_for_file = _file_handler(settings.log_file)
        handler_for_file.setFormatter(logging.Formatter("%(message)s"))
        file_logger.addHandler(handler_for_file)
        file_logger.setLevel(logging.INFO)
        file_processors = [_write_to_file]
    structlog.configure(
        processors=[
            *shared,
            *file_processors,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )

    handler = logging.StreamHandler()
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=[*shared, structlog.stdlib.add_logger_name],
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.format_exc_info,
                renderer,
            ],
        )
    )
    root = logging.getLogger()
    root.addHandler(handler)
    if settings.log_file:
        # Library and uvicorn logs go to the file too, as JSON.
        file_stdlib = _file_handler(settings.log_file)
        file_stdlib.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                foreign_pre_chain=[*shared, structlog.stdlib.add_logger_name],
                processors=[
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    structlog.processors.format_exc_info,
                    structlog.processors.JSONRenderer(),
                ],
            )
        )
        root.addHandler(file_stdlib)
    root.setLevel(level)
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True
    access = logging.getLogger("uvicorn.access")
    access.handlers = []
    access.propagate = False
    access.disabled = True


def get_logger(name: str) -> structlog.typing.FilteringBoundLogger:
    logger: structlog.typing.FilteringBoundLogger = structlog.get_logger(name)
    return logger
