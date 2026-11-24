"""Binance adapter checks on a recorded response. No network access."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import ccxt.async_support as ccxt
import pytest

from app.data.adapters.base import AdapterError, RawCandle
from app.data.adapters.binance import BinanceAdapter
from app.data.models import Timeframe
from tests.adapter_contract import assert_adapter_contract

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "binance_btcusdt_1h.json").read_text())
# The last fixture candle opens at 1795503600000 ms; "now" is mid-way through it.
NOW = datetime.fromtimestamp(1795503600 + 1800, tz=UTC)


class FakeExchange:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = responses
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    async def fetch_ohlcv(self, symbol: str, timeframe: str, **kwargs: Any) -> list[list[float]]:
        self.calls.append({"symbol": symbol, "timeframe": timeframe, **kwargs})
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response  # type: ignore[no-any-return]

    async def close(self) -> None:
        self.closed = True


def _adapter(exchange: FakeExchange, attempts: int = 3) -> BinanceAdapter:
    return BinanceAdapter(exchange, clock=lambda: NOW, attempts=attempts, max_wait_seconds=0.01)


async def test_meets_the_adapter_contract() -> None:
    adapter = _adapter(FakeExchange([FIXTURE]))

    await assert_adapter_contract(adapter, "BTC/USDT", Timeframe.H1, NOW)


async def test_drops_the_still_forming_candle() -> None:
    candles = await _adapter(FakeExchange([FIXTURE])).fetch_candles("BTC/USDT", Timeframe.H1)

    assert len(candles) == len(FIXTURE) - 1
    assert candles[-1].ts == datetime.fromtimestamp(1795500000, tz=UTC)


async def test_prices_are_exact_decimals_in_utc() -> None:
    candles = await _adapter(FakeExchange([FIXTURE])).fetch_candles("BTC/USDT", Timeframe.H1)

    assert candles[0] == RawCandle(
        ts=datetime.fromtimestamp(1795485600, tz=UTC),
        open=Decimal("61090.84"),
        high=Decimal("61120.0"),
        low=Decimal("60072.95"),
        close=Decimal("60074.9"),
        volume=Decimal("1444.16327"),
    )


async def test_passes_since_and_limit_to_the_exchange() -> None:
    exchange = FakeExchange([FIXTURE])
    since = datetime.fromtimestamp(1795485600, tz=UTC)

    await _adapter(exchange).fetch_candles("BTC/USDT", Timeframe.H1, since=since, limit=10)

    assert exchange.calls == [
        {"symbol": "BTC/USDT", "timeframe": "1h", "since": 1795485600000, "limit": 10}
    ]


async def test_retries_rate_limits_then_succeeds() -> None:
    exchange = FakeExchange(
        [ccxt.RateLimitExceeded("slow down"), ccxt.NetworkError("blip"), FIXTURE]
    )

    candles = await _adapter(exchange).fetch_candles("BTC/USDT", Timeframe.H1)

    assert len(exchange.calls) == 3
    assert candles


async def test_gives_up_after_the_attempt_limit() -> None:
    exchange = FakeExchange([ccxt.RateLimitExceeded("x")] * 3)

    with pytest.raises(AdapterError, match="RateLimitExceeded"):
        await _adapter(exchange, attempts=3).fetch_candles("BTC/USDT", Timeframe.H1)

    assert len(exchange.calls) == 3


async def test_does_not_retry_a_bad_symbol_and_hides_details() -> None:
    exchange = FakeExchange([ccxt.BadSymbol("secret-looking detail apikey=abc")])

    with pytest.raises(AdapterError) as info:
        await _adapter(exchange).fetch_candles("NOPE/USDT", Timeframe.H1)

    assert len(exchange.calls) == 1
    assert "apikey" not in str(info.value)


async def test_aclose_closes_the_exchange() -> None:
    exchange = FakeExchange([])

    await _adapter(exchange).aclose()

    assert exchange.closed


def test_a_naive_datetime_is_rejected() -> None:
    with pytest.raises(ValueError, match="UTC"):
        RawCandle(
            ts=datetime(2026, 1, 1),  # noqa: DTZ001 - the point of the test
            open=Decimal(1),
            high=Decimal(1),
            low=Decimal(1),
            close=Decimal(1),
            volume=Decimal(0),
        )
