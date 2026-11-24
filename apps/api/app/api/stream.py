"""Live candle updates over Server-Sent Events (works through proxies and tunnels, and the
browser reconnects on its own).

The stream service publishes every update of the forming 1m candle to Redis; this endpoint
relays them. Each message is the full latest candle, so when a client is slow we skip the
ones in between and send only the newest (nothing piles up in memory).
"""

import time
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis

from app.core.logging import get_logger
from app.core.redis import RedisDep
from app.data.universe import default_universe
from app.stream.writer import CHANNEL, LIVE_KEY

router = APIRouter(prefix="/data", tags=["data"])
logger = get_logger(__name__)

MAX_CLIENTS = 50
KEEPALIVE_SECONDS = 15.0
POLL_SECONDS = 1.0
VENUE = "binance"


def _event(data: str | bytes) -> str:
    text = data.decode() if isinstance(data, bytes) else data
    return f"event: candle\ndata: {text}\n\n"


async def candle_events(
    redis: Redis,
    symbol: str,
    is_disconnected: Callable[[], Awaitable[bool]],
    *,
    keepalive_seconds: float = KEEPALIVE_SECONDS,
    poll_seconds: float = POLL_SECONDS,
) -> AsyncIterator[str]:
    """SSE text chunks: the latest known candle first, then every update, then keepalives."""
    channel = CHANNEL.format(venue=VENUE, symbol=symbol)
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)
    try:
        initial = await redis.get(LIVE_KEY.format(venue=VENUE, symbol=symbol))
        if initial:
            yield _event(initial)
        last_sent = time.monotonic()
        while not await is_disconnected():
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=poll_seconds)
            latest = None
            while message is not None:  # drain what is already waiting; keep only the newest
                latest = message["data"]
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0)
            if latest is not None:
                yield _event(latest)
                last_sent = time.monotonic()
            elif time.monotonic() - last_sent >= keepalive_seconds:
                yield ": keepalive\n\n"
                last_sent = time.monotonic()
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()


@router.get(
    "/stream",
    summary="Live candle stream (SSE)",
    response_class=StreamingResponse,
    responses={
        200: {"content": {"text/event-stream": {}}, "description": "Server-Sent Events"},
        404: {"description": "Unknown symbol"},
        503: {"description": "Too many open streams"},
    },
)
async def stream(
    request: Request,
    redis: RedisDep,
    symbol: Annotated[str, Query(description="e.g. BTC/USDT")],
) -> StreamingResponse:
    """Server-Sent Events. Each `candle` event is the forming 1-minute candle as JSON with
    decimal-string prices: {"ts", "open", "high", "low", "close", "volume"}. A `: keepalive`
    comment is sent every 15 seconds of silence."""
    known = {s.symbol for s in default_universe(twelve_data_enabled=False) if s.venue == VENUE}
    if symbol not in known:
        raise HTTPException(status_code=404, detail="Unknown symbol")
    state = request.app.state
    if getattr(state, "stream_clients", 0) >= MAX_CLIENTS:
        raise HTTPException(status_code=503, detail="Too many open streams")

    async def body() -> AsyncIterator[str]:
        state.stream_clients = getattr(state, "stream_clients", 0) + 1
        try:
            async for chunk in candle_events(redis, symbol, request.is_disconnected):
                yield chunk
        finally:
            state.stream_clients -= 1

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
