"""Quality checks with the database layer faked out (the SQL runs in the integration tests)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.data.models import AssetClass, Timeframe
from app.data.quality import QualityReport, check_instrument
from app.data.universe import InstrumentSpec

NOW = datetime(2026, 3, 2, 12, 30, tzinfo=UTC)  # a Monday
CRYPTO = InstrumentSpec("binance", "BTC/USDT", AssetClass.CRYPTO)
GOLD = InstrumentSpec("twelvedata", "XAU/USD", AssetClass.GOLD)


class FakeSession:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    async def execute(self, *_: Any, **__: Any) -> Any:
        return SimpleNamespace(all=lambda: self._rows)


async def _check(rows: list[Any], spec: InstrumentSpec, now: datetime) -> QualityReport:
    return await check_instrument(cast(AsyncSession, FakeSession(rows)), spec, Timeframe.H1, now)


def _row(ts: datetime, close: str = "100", **overrides: str) -> Any:
    values = {"open": "100", "high": "101", "low": "99", "close": close} | overrides
    return SimpleNamespace(ts=ts, **{k: Decimal(v) for k, v in values.items()})


def _hourly(count: int, end: datetime = NOW) -> list[Any]:
    last = end.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    return [_row(last - timedelta(hours=i)) for i in reversed(range(count))]


async def test_clean_data_is_ok() -> None:
    report = await _check(_hourly(48), CRYPTO, NOW)

    assert report.ok
    assert report.candles == 48
    assert report.missing_candles == 0


async def test_no_data_is_not_ok() -> None:
    report = await _check([], CRYPTO, NOW)

    assert not report.ok
    assert report.candles == 0
    assert report.stale


async def test_a_hole_is_counted() -> None:
    rows = [r for i, r in enumerate(_hourly(48)) if i not in (10, 11, 20)]

    report = await _check(rows, CRYPTO, NOW)

    assert report.missing_candles == 3
    assert report.gap_runs == 2
    assert not report.ok


async def test_old_latest_candle_is_stale() -> None:
    old = NOW - timedelta(hours=10)

    report = await _check(_hourly(5, end=old), CRYPTO, NOW)

    assert report.stale
    assert not report.ok


async def test_gold_is_not_stale_while_the_market_is_closed() -> None:
    saturday = datetime(2026, 3, 7, 12, 0, tzinfo=UTC)
    friday_close = datetime(2026, 3, 6, 22, 0, tzinfo=UTC)

    report = await _check(_hourly(24, end=friday_close), GOLD, saturday)

    assert not report.stale
    assert report.missing_candles == 0


async def test_inconsistent_candle_is_flagged() -> None:
    rows = _hourly(10)
    rows[3] = _row(rows[3].ts, close="150")  # close above the high

    report = await _check(rows, CRYPTO, NOW)

    assert report.inconsistent_candles == 1
    assert not report.ok


async def test_price_spike_is_flagged() -> None:
    rows = _hourly(10)
    rows[5] = _row(rows[5].ts, close="100", open="100", high="101", low="99")
    rows[6] = _row(rows[6].ts, close="200", open="100", high="201", low="99")  # +100%

    report = await _check(rows, CRYPTO, NOW)

    assert report.spikes >= 1
    assert not report.ok
