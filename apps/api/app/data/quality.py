"""Data-quality checks on stored candles over the last 30 days.

Duplicate candles cannot exist (the primary key rejects them), so they are not checked here.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from itertools import pairwise

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.gaps import find_gaps, market_closed
from app.data.models import Candle, Instrument, Timeframe
from app.data.universe import InstrumentSpec

WINDOW_DAYS = 30
# A move bigger than this between consecutive closes is flagged as a possible bad tick.
SPIKE_THRESHOLD = {
    Timeframe.M1: Decimal("0.05"),
    Timeframe.M5: Decimal("0.08"),
    Timeframe.H1: Decimal("0.15"),
    Timeframe.D1: Decimal("0.30"),
}
STALE_AFTER_CANDLES = 3


@dataclass(frozen=True, slots=True)
class QualityReport:
    venue: str
    symbol: str
    timeframe: str
    candles: int
    latest: datetime | None
    missing_candles: int
    gap_runs: int
    stale: bool
    inconsistent_candles: int
    spikes: int

    @property
    def ok(self) -> bool:
        return (
            self.candles > 0
            and not self.stale
            and self.missing_candles == 0
            and self.inconsistent_candles == 0
            and self.spikes == 0
        )


async def check_instrument(
    session: AsyncSession, spec: InstrumentSpec, timeframe: Timeframe, now: datetime | None = None
) -> QualityReport:
    now = (now or datetime.now(UTC)).astimezone(UTC)
    start = now - timedelta(days=WINDOW_DAYS)
    rows = (
        await session.execute(
            select(Candle.ts, Candle.open, Candle.high, Candle.low, Candle.close)
            .join(Instrument, Instrument.id == Candle.instrument_id)
            .where(
                Instrument.venue == spec.venue,
                Instrument.symbol == spec.symbol,
                Candle.timeframe == timeframe.value,
                Candle.ts >= start,
                Candle.ts < now,
            )
            .order_by(Candle.ts)
        )
    ).all()

    if not rows:
        return QualityReport(spec.venue, spec.symbol, timeframe.value, 0, None, 0, 0, True, 0, 0)

    times = [row.ts for row in rows]
    # Holes are only meaningful inside the history we hold.
    gaps = find_gaps(times, spec.venue, timeframe, times[0], now)
    inconsistent = sum(
        1 for r in rows if not (r.low <= r.open <= r.high and r.low <= r.close <= r.high)
    )
    threshold = SPIKE_THRESHOLD[timeframe]
    spikes = sum(
        1
        for previous, current in pairwise(rows)
        if previous.close > 0 and abs(current.close / previous.close - 1) > threshold
    )
    latest = times[-1]
    overdue = (now - latest).total_seconds() > STALE_AFTER_CANDLES * timeframe.seconds
    return QualityReport(
        venue=spec.venue,
        symbol=spec.symbol,
        timeframe=timeframe.value,
        candles=len(rows),
        latest=latest,
        missing_candles=sum(gap.count for gap in gaps),
        gap_runs=len(gaps),
        stale=overdue and not market_closed(spec.venue, now),
        inconsistent_candles=inconsistent,
        spikes=spikes,
    )
