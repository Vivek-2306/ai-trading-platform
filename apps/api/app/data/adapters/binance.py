"""Binance public market data through ccxt. Needs no API key."""

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import ccxt.async_support as ccxt
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.logging import get_logger
from app.data.adapters.base import AdapterError, RawCandle
from app.data.models import Timeframe

logger = get_logger(__name__)

# Rate limits and network blips are worth retrying; bad symbols and the like are not.
_RETRYABLE = (ccxt.RateLimitExceeded, ccxt.DDoSProtection, ccxt.NetworkError)


def _now() -> datetime:
    return datetime.now(UTC)


class BinanceAdapter:
    venue = "binance"

    def __init__(
        self,
        exchange: Any | None = None,
        *,
        clock: Callable[[], datetime] = _now,
        attempts: int = 5,
        max_wait_seconds: float = 30.0,
    ) -> None:
        # ccxt's own rate limiter spaces requests out; retries cover what slips through.
        self._exchange = exchange or ccxt.binance({"enableRateLimit": True})
        self._clock = clock
        self._attempts = attempts
        self._max_wait = max_wait_seconds

    async def fetch_candles(
        self, symbol: str, timeframe: Timeframe, since: datetime | None = None, limit: int = 500
    ) -> list[RawCandle]:
        since_ms = int(since.timestamp() * 1000) if since else None
        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception_type(_RETRYABLE),
                stop=stop_after_attempt(self._attempts),
                wait=wait_exponential(multiplier=1, max=self._max_wait),
                before_sleep=self._log_retry,
                reraise=True,
            ):
                with attempt:
                    rows = await self._exchange.fetch_ohlcv(
                        symbol, timeframe.value, since=since_ms, limit=limit
                    )
        except RetryError as exc:  # pragma: no cover - reraise=True makes this unreachable
            raise AdapterError(f"binance {symbol} {timeframe.value}: retries exhausted") from exc
        except ccxt.BaseError as exc:
            # Message only: ccxt errors can echo request details.
            raise AdapterError(f"binance {symbol} {timeframe.value}: {type(exc).__name__}") from exc
        return self._closed(rows, timeframe)

    def _closed(self, rows: list[list[float]], timeframe: Timeframe) -> list[RawCandle]:
        now = self._clock()
        candles: list[RawCandle] = []
        for ts_ms, o, h, low, c, v in rows:
            opened = datetime.fromtimestamp(ts_ms / 1000, tz=UTC)
            if (now - opened).total_seconds() < timeframe.seconds:
                continue  # still forming
            # ccxt hands back floats parsed from Binance's decimal strings; str() round-trips.
            candles.append(
                RawCandle(
                    ts=opened,
                    open=Decimal(str(o)),
                    high=Decimal(str(h)),
                    low=Decimal(str(low)),
                    close=Decimal(str(c)),
                    volume=Decimal(str(v)),
                )
            )
        return sorted(candles, key=lambda candle: candle.ts)

    @staticmethod
    def _log_retry(retry_state: Any) -> None:
        error = retry_state.outcome.exception()
        logger.warning(
            "market_data_retry",
            venue="binance",
            attempt=retry_state.attempt_number,
            error=type(error).__name__,
        )

    async def aclose(self) -> None:
        await self._exchange.close()
