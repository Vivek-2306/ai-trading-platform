"""The contract every market data source implements.

Callers depend on this interface only, so adding an exchange never changes them.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol

from app.data.models import Timeframe


class AdapterError(Exception):
    """A data source failed in a way retries did not fix. Never carries credentials."""


@dataclass(frozen=True, slots=True)
class RawCandle:
    """One OHLCV bar as returned by a source. `ts` is the open time, timezone-aware UTC."""

    ts: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    def __post_init__(self) -> None:
        if self.ts.tzinfo is None or self.ts.utcoffset() != UTC.utcoffset(None):
            raise ValueError("candle time must be timezone-aware UTC")


class MarketDataAdapter(Protocol):
    """Fetches closed candles. An unfinished (still forming) candle is never returned."""

    venue: str

    async def fetch_candles(
        self, symbol: str, timeframe: Timeframe, since: datetime | None = None, limit: int = 500
    ) -> list[RawCandle]:
        """Closed candles with open time >= `since`, oldest first, at most `limit`."""
        ...

    async def aclose(self) -> None:
        """Release network resources."""
        ...
