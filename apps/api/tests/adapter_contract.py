"""Checks every MarketDataAdapter must pass. Each adapter's test module calls this."""

from datetime import UTC, datetime
from decimal import Decimal

from app.data.adapters.base import MarketDataAdapter
from app.data.models import Timeframe


async def assert_adapter_contract(
    adapter: MarketDataAdapter, symbol: str, timeframe: Timeframe, now: datetime
) -> None:
    candles = await adapter.fetch_candles(symbol, timeframe)

    assert candles, "fixture should contain closed candles"
    times = [candle.ts for candle in candles]
    assert times == sorted(times), "oldest first"
    assert len(set(times)) == len(times), "no duplicate candles"
    for candle in candles:
        assert candle.ts.tzinfo is not None and candle.ts.utcoffset() == UTC.utcoffset(None)
        assert all(
            isinstance(value, Decimal)
            for value in (candle.open, candle.high, candle.low, candle.close, candle.volume)
        )
        assert candle.high >= candle.low
        assert (now - candle.ts).total_seconds() >= timeframe.seconds, "closed candles only"
