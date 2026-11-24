"""Which candles should exist, and which are missing.

Crypto trades 24/7. Spot gold (Twelve Data) is closed from Friday 22:00 UTC to Sunday 22:00 UTC,
so candles that open in that window are not expected and their absence is not a gap. This is
an approximation of the real forex week; it errs on the side of not raising false alarms.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.data.models import Timeframe

# Venues whose market closes at the weekend. Binance (including PAXG) never closes.
_WEEKEND_CLOSED_VENUES = {"twelvedata"}
_FRIDAY, _SATURDAY, _SUNDAY = 4, 5, 6
_CLOSE_HOUR_UTC = 22


@dataclass(frozen=True, slots=True)
class Gap:
    """Missing candles from `start` to `end` (both are candle open times, inclusive)."""

    start: datetime
    end: datetime
    count: int


def market_closed(venue: str, ts: datetime) -> bool:
    """True if a candle opening at `ts` is not expected because the market is shut."""
    if venue not in _WEEKEND_CLOSED_VENUES:
        return False
    ts = ts.astimezone(UTC)
    weekday = ts.weekday()
    if weekday == _SATURDAY:
        return True
    if weekday == _FRIDAY:
        return ts.hour >= _CLOSE_HOUR_UTC
    if weekday == _SUNDAY:
        return ts.hour < _CLOSE_HOUR_UTC
    return False


def _aligned_start(start: datetime, step: int) -> datetime:
    epoch = int(start.timestamp())
    remainder = epoch % step
    aligned = epoch if remainder == 0 else epoch + step - remainder
    return datetime.fromtimestamp(aligned, tz=UTC)


def find_gaps(
    existing: Iterable[datetime],
    venue: str,
    timeframe: Timeframe,
    start: datetime,
    end: datetime,
) -> list[Gap]:
    """Missing, expected candles that opened at or after `start` and closed by `end`, as runs."""
    step = timeframe.seconds
    have = {ts.astimezone(UTC) for ts in existing}
    gaps: list[Gap] = []
    run_start: datetime | None = None
    run_end: datetime | None = None
    run_count = 0
    ts = _aligned_start(start, step)
    while ts + timedelta(seconds=step) <= end:  # a candle still forming is not missing
        missing = ts not in have and not market_closed(venue, ts)
        if missing:
            if run_start is None:
                run_start = ts
            run_end = ts
            run_count += 1
        elif run_start is not None and run_end is not None and not market_closed(venue, ts):
            gaps.append(Gap(run_start, run_end, run_count))
            run_start = run_end = None
            run_count = 0
        ts += timedelta(seconds=step)
    if run_start is not None and run_end is not None:
        gaps.append(Gap(run_start, run_end, run_count))
    return gaps
