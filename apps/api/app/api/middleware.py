"""Request context: a request ID on every request, its log lines and its response."""

import re
import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger

REQUEST_ID_HEADER = "X-Request-ID"
# Reuse a caller's ID only if it looks sane; never echo arbitrary input into logs.
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

_PROBE_PATHS = frozenset({"/health", "/health/ready"})

logger = get_logger(__name__)


def resolve_request_id(incoming: str | None) -> str:
    if incoming and _VALID_REQUEST_ID.fullmatch(incoming):
        return incoming
    return uuid.uuid4().hex


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = resolve_request_id(request.headers.get(REQUEST_ID_HEADER))
        # Stored on request.state too, so error handlers outside this middleware can read it.
        request.state.request_id = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id, method=request.method, path=request.url.path
        )

        started = time.perf_counter()
        status = 500  # if the route raises, the error handler answers with a 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            # Probes hit the health endpoints every few seconds: keep the healthy ones out of
            # normal logs, but never hide a failing probe.
            quiet = request.url.path in _PROBE_PATHS and status < 400
            log = logger.debug if quiet else logger.info
            log("request", status=status, duration_ms=duration_ms)
            structlog.contextvars.clear_contextvars()
