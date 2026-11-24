"""Stream candle updates from an exchange WebSocket, reconnecting after failures.

Each symbol has its own loop, so one failing symbol does not stop the others. The exchange
object is ccxt.pro's (or a test fake) and is injected.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

import ccxt.async_support as ccxt
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError

from app.core.logging import get_logger

logger = get_logger(__name__)

# One update from ccxt: a list of [open_time_ms, open, high, low, close, volume] rows, the
# newest being the candle that is still forming.
Rows = list[list[float]]
Handler = Callable[[str, Rows], Awaitable[None]]

# Network trouble and exchange hiccups: wait and reconnect. Anything else is a bug and is
# allowed to crash the service so it gets noticed (the container restarts it).
_RECOVERABLE = (ccxt.NetworkError, ccxt.ExchangeNotAvailable, ccxt.RequestTimeout, TimeoutError)


# Redis or the database hiccuping while storing an update: log it and carry on; the gap
# healer repairs whatever was missed.
_STORE_ERRORS = (RedisError, SQLAlchemyError, OSError)


class StreamStalledError(Exception):
    """No update arrived from any symbol for too long. Raised so the process exits and the
    container restarts (a hung WebSocket otherwise stays 'unhealthy' forever)."""


class StreamService:
    def __init__(
        self,
        exchange: Any,
        symbols: list[str],
        handler: Handler,
        *,
        on_alive: Callable[[], Awaitable[None]] | None = None,
        on_reconnect: Callable[[], None] | None = None,
        timeframe: str = "1m",
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        initial_backoff: float = 1.0,
        max_backoff: float = 30.0,
        stall_seconds: float = 180.0,
    ) -> None:
        self._exchange = exchange
        self._symbols = symbols
        self._handler = handler
        self._on_alive = on_alive
        self._on_reconnect = on_reconnect
        self._timeframe = timeframe
        self._sleep = sleep
        self._initial_backoff = initial_backoff
        self._max_backoff = max_backoff
        self._stall_seconds = stall_seconds
        self._last_message = time.monotonic()
        self._stopping = asyncio.Event()
        self._tasks: list[asyncio.Task[None]] = []

    def stop(self) -> None:
        """Stop now: a watcher blocked waiting for a quiet symbol's next update is cancelled."""
        self._stopping.set()
        for task in self._tasks:
            task.cancel()

    async def run(self) -> None:
        """Stream until `stop()` is called."""
        logger.info("stream_started", symbols=self._symbols, timeframe=self._timeframe)
        async with asyncio.TaskGroup() as group:
            self._last_message = time.monotonic()
            for symbol in self._symbols:
                self._tasks.append(group.create_task(self._watch(symbol)))
            self._tasks.append(group.create_task(self._watchdog()))
        logger.info("stream_stopped")

    async def _watchdog(self) -> None:
        try:
            while not self._stopping.is_set():
                await asyncio.sleep(max(self._stall_seconds / 4, 0.01))
                silent = time.monotonic() - self._last_message
                if silent > self._stall_seconds:
                    logger.error("stream_stalled", silent_seconds=int(silent))
                    raise StreamStalledError(f"no updates for {int(silent)}s")
        except asyncio.CancelledError:
            if not self._stopping.is_set():
                raise

    async def _watch(self, symbol: str) -> None:
        try:
            await self._watch_forever(symbol)
        except asyncio.CancelledError:
            if not self._stopping.is_set():
                raise  # cancelled from outside, not by stop()

    async def _watch_forever(self, symbol: str) -> None:
        backoff = self._initial_backoff
        dropped = False
        while not self._stopping.is_set():
            try:
                rows = await self._exchange.watch_ohlcv(symbol, self._timeframe)
            except _RECOVERABLE as exc:
                logger.warning(
                    "stream_disconnected",
                    symbol=symbol,
                    error=type(exc).__name__,
                    retry_in=backoff,
                )
                dropped = True
                await self._sleep(backoff)
                backoff = min(backoff * 2, self._max_backoff)
                continue
            backoff = self._initial_backoff  # a message arrived: the connection is healthy
            self._last_message = time.monotonic()
            if dropped:
                dropped = False
                logger.info("stream_reconnected", symbol=symbol)
                if self._on_reconnect is not None:
                    self._on_reconnect()  # candles may have been missed: ask for a gap check
            try:
                if self._on_alive is not None:
                    await self._on_alive()
                await self._handler(symbol, rows)
            except _STORE_ERRORS as exc:
                logger.warning("stream_store_failed", symbol=symbol, error=type(exc).__name__)
                if self._on_reconnect is not None:
                    self._on_reconnect()  # ask the healer to repair what this missed
