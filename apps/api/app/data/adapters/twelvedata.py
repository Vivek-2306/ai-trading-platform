"""Twelve Data candles (used for XAU/USD gold). Needs a free API key in TWELVE_DATA_API_KEY.

Free plan (checked 2026-11-24): 8 credits per minute and 800 per day; one time_series call
costs 1 credit per symbol. Forex pairs have no volume, so volume is stored as 0.
"""

import asyncio
import time
from datetime import UTC, datetime
from decimal import Decimal

import httpx
from pydantic import SecretStr
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.logging import get_logger
from app.data.adapters.base import AdapterError, RawCandle
from app.data.models import Timeframe

logger = get_logger(__name__)

BASE_URL = "https://api.twelvedata.com"
_INTERVALS = {
    Timeframe.M1: "1min",
    Timeframe.M5: "5min",
    Timeframe.H1: "1h",
    Timeframe.D1: "1day",
}


class _RetryableError(Exception):
    """Rate limit, 5xx or network blip. The message never holds the request URL (it has the key)."""


def _parse_time(text: str) -> datetime:
    """'2026-11-24 10:00:00' (hourly and finer) or '2026-11-24' (daily), both UTC."""
    fmt = "%Y-%m-%d %H:%M:%S" if " " in text else "%Y-%m-%d"
    return datetime.strptime(text, fmt).replace(tzinfo=UTC)


class TwelveDataAdapter:
    venue = "twelvedata"

    def __init__(
        self,
        api_key: SecretStr,
        client: httpx.AsyncClient | None = None,
        *,
        attempts: int = 4,
        max_wait_seconds: float = 30.0,
        min_interval_seconds: float = 8.0,
    ) -> None:
        self._key = api_key
        self._client = client or httpx.AsyncClient(base_url=BASE_URL, timeout=15)
        self._attempts = attempts
        self._max_wait = max_wait_seconds
        # Free plan: 8 credits per minute. One call a few seconds apart stays under it.
        self._min_interval = min_interval_seconds
        self._last_call = float("-inf")

    async def fetch_candles(
        self, symbol: str, timeframe: Timeframe, since: datetime | None = None, limit: int = 500
    ) -> list[RawCandle]:
        params = {
            "symbol": symbol,
            "interval": _INTERVALS[timeframe],
            "outputsize": str(min(limit, 5000)),
            "timezone": "UTC",
            "order": "ASC",
            "apikey": self._key.get_secret_value(),
        }
        if since is not None:
            params["start_date"] = since.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")
        label = f"twelvedata {symbol} {timeframe.value}"
        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception_type(_RetryableError),
                stop=stop_after_attempt(self._attempts),
                wait=wait_exponential(multiplier=2, max=self._max_wait),
                reraise=True,
            ):
                with attempt:
                    payload = await self._get(params)
        except _RetryableError as exc:
            raise AdapterError(f"{label}: {exc}") from exc
        return self._closed(payload, timeframe, label)

    async def _get(self, params: dict[str, str]) -> dict[str, object]:
        wait = self._last_call + self._min_interval - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_call = time.monotonic()
        failure: str | None = None
        try:
            response = await self._client.get("/time_series", params=params)
        except httpx.HTTPError as exc:
            # httpx errors can quote the request URL, which contains the API key: keep the
            # type only, and raise outside this block so the original is not chained.
            failure = type(exc).__name__
        if failure is not None:
            raise _RetryableError(failure)
        if response.status_code == 429:
            raise _RetryableError("rate limited")
        if response.status_code >= 500:
            raise _RetryableError(f"HTTP {response.status_code}")
        if response.status_code >= 400:
            raise AdapterError(f"twelvedata HTTP {response.status_code}")
        try:
            data: dict[str, object] = response.json()
        except ValueError:
            raise AdapterError("twelvedata: response was not JSON") from None
        # Twelve Data reports most errors inside a 200 response.
        if data.get("status") == "error":
            code = data.get("code")
            if code == 429:
                raise _RetryableError("rate limited")
            if code == 400 and "no data" in str(data.get("message", "")).lower():
                return {"values": []}  # nothing new yet (weekend, or the bar is not out)
            raise AdapterError(f"twelvedata error code {code}")
        return data

    @staticmethod
    def _closed(payload: dict[str, object], timeframe: Timeframe, label: str) -> list[RawCandle]:
        values = payload.get("values")
        if not isinstance(values, list):
            raise AdapterError(f"{label}: unexpected response shape")
        now = datetime.now(UTC)
        candles: list[RawCandle] = []
        for row in values:
            try:
                opened = _parse_time(row["datetime"])
                if (now - opened).total_seconds() < timeframe.seconds:
                    continue  # still forming
                candles.append(
                    RawCandle(
                        ts=opened,
                        open=Decimal(row["open"]),
                        high=Decimal(row["high"]),
                        low=Decimal(row["low"]),
                        close=Decimal(row["close"]),
                        volume=Decimal(row.get("volume") or 0),
                    )
                )
            except (KeyError, TypeError, ValueError, ArithmeticError):
                raise AdapterError(f"{label}: malformed candle row") from None
        return sorted(candles, key=lambda candle: candle.ts)

    async def aclose(self) -> None:
        await self._client.aclose()
