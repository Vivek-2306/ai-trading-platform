"""Turn stream updates into stored data.

ccxt delivers only the candles that changed since the last update, normally one row: the
candle still forming. So the writer remembers the last row it saw per symbol.

- The forming candle goes to Redis (latest value, plus a pub/sub message for live consumers).
- When a row with a newer open time arrives, the remembered candle has closed and is written
  to the database, but only if its last update arrived at or after its close time. A candle
  whose last update came earlier (a disconnect cut it short) may be missing its final ticks,
  so it is skipped and left for the REST gap backfill, which stores exact values.
- Writes skip candles that already exist, so a restart that replays old candles cannot
  create duplicates.
"""

import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from redis.asyncio import Redis

from app.core.logging import get_logger
from app.data.adapters.base import RawCandle
from app.data.adapters.binance import ohlcv_row_to_candle
from app.stream.service import Rows

logger = get_logger(__name__)

LIVE_KEY = "live:{venue}:{symbol}:1m"
CHANNEL = "candles:{venue}:{symbol}:1m"
LIVE_TTL_SECONDS = 300
CANDLE_MS = 60_000
# Our clock may run a little behind the exchange's, so a final update can look slightly early.
CLOCK_TOLERANCE_MS = 1_000

# Stores closed candles for a symbol; returns how many were new.
Persist = Callable[[str, list[RawCandle]], Awaitable[int]]


def live_payload(candle: RawCandle) -> str:
    """The JSON shape shared by the Redis value and the pub/sub message (prices as strings)."""
    return json.dumps(
        {
            "ts": candle.ts.isoformat(),
            "open": str(candle.open),
            "high": str(candle.high),
            "low": str(candle.low),
            "close": str(candle.close),
            "volume": str(candle.volume),
        }
    )


@dataclass(slots=True)
class _Seen:
    row: list[float]
    received_ms: float


def _wall_clock_ms() -> float:
    return time.time() * 1000


class CandleWriter:
    def __init__(
        self,
        redis: Redis,
        persist: Persist,
        venue: str = "binance",
        clock_ms: Callable[[], float] = _wall_clock_ms,
    ) -> None:
        self._redis = redis
        self._persist = persist
        self._venue = venue
        self._clock_ms = clock_ms
        self._current: dict[str, _Seen] = {}

    async def handle(self, symbol: str, rows: Rows) -> None:
        now = self._clock_ms()
        for row in sorted(rows, key=lambda r: r[0]):
            await self._apply(symbol, row, now)

    async def _apply(self, symbol: str, row: list[float], now: float) -> None:
        current = self._current.get(symbol)
        if current is not None and row[0] < current.row[0]:
            return  # a replay of an older candle: ignore
        if current is not None and row[0] > current.row[0]:
            await self._close(symbol, current)
        self._current[symbol] = _Seen(row, now)
        payload = live_payload(ohlcv_row_to_candle(row))
        await self._redis.set(
            LIVE_KEY.format(venue=self._venue, symbol=symbol), payload, ex=LIVE_TTL_SECONDS
        )
        await self._redis.publish(CHANNEL.format(venue=self._venue, symbol=symbol), payload)

    async def _close(self, symbol: str, seen: _Seen) -> None:
        close_ms = seen.row[0] + CANDLE_MS
        if seen.received_ms < close_ms - CLOCK_TOLERANCE_MS:
            logger.warning(
                "stream_candle_incomplete",
                symbol=symbol,
                open_ms=int(seen.row[0]),
                last_update_ms_before_close=int(close_ms - seen.received_ms),
            )
            return  # the gap backfill will store the exact candle
        new = await self._persist(symbol, [ohlcv_row_to_candle(seen.row)])
        logger.debug("stream_candle_stored", symbol=symbol, open_ms=int(seen.row[0]), new=new)
