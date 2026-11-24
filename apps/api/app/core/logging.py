"""Structured logging with structlog.

Production writes one JSON object per line (easy to ship to a log service); development
writes readable, coloured lines. Request-scoped values (request ID, method, path) are bound
with structlog's contextvars and appear on every log line for that request.
"""

import logging
import logging.handlers
import re
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
# Key names (lower-cased, "-" treated as "_") containing any of these have their value hidden.
_SENSITIVE_KEYS = (
    "password",
    "passwd",
    "passphrase",
    "secret",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "access_key",
    "credential",
    "authorization",
    "cookie",
    "jwt",
    "dsn",
)
# Counters such as max_tokens / tokens_used are not secrets.
_COUNTER_HINT = "tokens"
# Secrets that sit inside text: URLs with a password, bearer tokens, key=value pairs.
_SECRET_IN_TEXT = (
    (re.compile(r"(://[^/\s:@]+:)[^@\s/]+@"), r"\1" + REDACTED + "@"),
    (re.compile(r"(?i)\b(bearer\s+)\S+"), r"\1" + REDACTED),
    (re.compile(r"(?i)\b((?:token|api_?key|password|secret)=)[^&\s]+"), r"\1" + REDACTED),
)
_FILE_LOGGER = "aitp.logfile"
# Handlers this module added, so reconfiguring never removes anyone else's (pytest, Celery...).
_own_handlers: list[tuple[logging.Logger, logging.Handler]] = []
_file_logging_on = False


def _is_sensitive_key(key: object) -> bool:
    if not isinstance(key, str):
        return False
    name = key.lower().replace("-", "_")
    if _COUNTER_HINT in name:
        return False
    return any(part in name for part in _SENSITIVE_KEYS)


def _scrub_text(text: str) -> str:
    for pattern, replacement in _SECRET_IN_TEXT:
        text = pattern.sub(replacement, text)
    return text


def redact_value(value: Any) -> Any:
    """Hide secrets by key name (any depth) and inside text values."""
    if isinstance(value, dict):
        return {
            key: REDACTED if _is_sensitive_key(key) else redact_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple | set | frozenset):
        return [redact_value(item) for item in value]
    if isinstance(value, str):
        return _scrub_text(value)
    return value


def redact_secrets(
    _logger: object, _method: str, event_dict: structlog.typing.EventDict
) -> structlog.typing.EventDict:
    """structlog processor: runs after tracebacks are rendered, so those are scrubbed too."""
    redacted: structlog.typing.EventDict = redact_value(event_dict)
    return redacted


class _FileFormatter(structlog.stdlib.ProcessorFormatter):
    """One file handler for both sources: structlog lines arrive already rendered as JSON."""

    def format(self, record: logging.LogRecord) -> str:
        if record.name == _FILE_LOGGER:
            return record.getMessage()
        return super().format(record)


def _write_to_file(
    _logger: object, _method: str, event_dict: structlog.typing.EventDict
) -> structlog.typing.EventDict:
    """Copy each structlog line, as JSON, to the log file (a no-op when none is configured)."""
    if _file_logging_on:
        logging.getLogger(_FILE_LOGGER).info(
            structlog.processors.JSONRenderer()(_logger, _method, dict(event_dict))
        )
    return event_dict


def _add_handler(logger: logging.Logger, handler: logging.Handler) -> None:
    logger.addHandler(handler)
    _own_handlers.append((logger, handler))


def _remove_own_handlers() -> None:
    """Remove and close handlers from an earlier configure call (releases the log file)."""
    while _own_handlers:
        logger, handler = _own_handlers.pop()
        logger.removeHandler(handler)
        handler.close()


def configure_logging(settings: Settings) -> None:
    """Configure structlog for this process. Safe to call more than once.

    Standard-library loggers (uvicorn, libraries) are routed through the same renderer, so
    production output is JSON only. Uvicorn's access log is silenced: the request
    middleware already logs every request once, with its request ID. With LOG_FILE set, every
    line is also written to that file as JSON, through one rotating handler. Use a different
    file per process (API, worker, beat): rotation is not safe across processes.
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
    ]
    global _file_logging_on
    _remove_own_handlers()
    _file_logging_on = bool(settings.log_file)
    file_handler: logging.Handler | None = None
    if settings.log_file:
        Path(settings.log_file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            settings.log_file, maxBytes=10_000_000, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(
            _FileFormatter(
                foreign_pre_chain=[*shared, structlog.stdlib.add_logger_name],
                processors=[
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    structlog.processors.format_exc_info,
                    redact_secrets,
                    structlog.processors.JSONRenderer(),
                ],
            )
        )
        file_logger = logging.getLogger(_FILE_LOGGER)
        file_logger.propagate = False
        file_logger.setLevel(logging.INFO)
        _add_handler(file_logger, file_handler)

    structlog.configure(
        processors=[
            *shared,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            redact_secrets,
            _write_to_file,
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
                redact_secrets,
                renderer,
            ],
        )
    )
    root = logging.getLogger()
    _add_handler(root, handler)
    if file_handler:
        root.addHandler(file_handler)
        _own_handlers.append((root, file_handler))
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
