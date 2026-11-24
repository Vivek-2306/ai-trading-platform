"""Backfill paging logic with a fake source and an in-memory sink."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from structlog.testing import capture_logs

from app.data.adapters.base import RawCandle
from app.data.backfill import backfill, years_ago
from app.data.models import Timeframe

T0 = datetime(2026, 1, 1, tzinfo=UTC)
HOUR = timedelta(hours=1)


def _candle(ts: datetime) -> RawCandle:
    return RawCandle(ts, Decimal(1), Decimal(2), Decimal(1), Decimal(2), Decimal(1))


class FakeAdapter:
    venue = "fake"

    def __init__(self, count: int) -> None:
        self._all = [_candle(T0 + HOUR * i) for i in range(count)]
        self.calls: list[tuple[datetime | None, int]] = []

    async def fetch_candles(
        self, symbol: str, timeframe: Timeframe, since: datetime | None = None, limit: int = 500
    ) -> list[RawCandle]:
        self.calls.append((since, limit))
        assert since is not None
        return [c for c in self._all if c.ts >= since][:limit]

    async def aclose(self) -> None: ...


class MemorySink:
    def __init__(self) -> None:
        self.stored: dict[datetime, RawCandle] = {}

    async def __call__(self, candles: list[RawCandle]) -> int:
        new = [c for c in candles if c.ts not in self.stored]
        self.stored.update({c.ts: c for c in new})
        return len(new)


async def test_pages_through_all_history() -> None:
    adapter, sink = FakeAdapter(2500), MemorySink()

    added = await backfill(adapter, "X", Timeframe.H1, T0, sink, page_size=1000)

    assert added == 2500
    assert len(sink.stored) == 2500
    assert [call[0] for call in adapter.calls] == [T0, T0 + HOUR * 1000, T0 + HOUR * 2000]


async def test_running_again_adds_nothing() -> None:
    adapter, sink = FakeAdapter(1500), MemorySink()
    await backfill(adapter, "X", Timeframe.H1, T0, sink, page_size=1000)

    again = await backfill(adapter, "X", Timeframe.H1, T0, sink, page_size=1000)

    assert again == 0
    assert len(sink.stored) == 1500


async def test_an_empty_source_stops_immediately() -> None:
    adapter, sink = FakeAdapter(0), MemorySink()

    assert await backfill(adapter, "X", Timeframe.H1, T0, sink) == 0
    assert len(adapter.calls) == 1


async def test_a_source_that_ignores_since_cannot_loop_forever() -> None:
    class Stuck(FakeAdapter):
        async def fetch_candles(
            self, symbol: str, timeframe: Timeframe, since: datetime | None = None, limit: int = 500
        ) -> list[RawCandle]:
            self.calls.append((since, limit))
            return self._all[:limit]  # always the same first page

    adapter, sink = Stuck(10), MemorySink()

    await backfill(adapter, "X", Timeframe.H1, T0, sink, page_size=5)

    assert len(adapter.calls) <= 3


async def test_progress_is_logged() -> None:
    with capture_logs() as logs:
        await backfill(FakeAdapter(5), "X", Timeframe.H1, T0, MemorySink(), page_size=1000)

    events = [log["event"] for log in logs]
    assert "backfill_progress" in events
    assert events[-1] == "backfill_done"


def test_years_ago() -> None:
    now = datetime(2026, 6, 1, tzinfo=UTC)

    assert years_ago(1, now) == now - timedelta(days=365.25)
