"""Gap detection and market hours."""

from datetime import UTC, datetime, timedelta

from app.data.gaps import Gap, find_gaps, market_closed
from app.data.models import Timeframe

# 2026-01-05 is a Monday.
MON = datetime(2026, 1, 5, tzinfo=UTC)
HOUR = timedelta(hours=1)


def _hours(start: datetime, count: int) -> list[datetime]:
    return [start + HOUR * i for i in range(count)]


def test_crypto_never_closes() -> None:
    saturday = datetime(2026, 1, 10, 12, tzinfo=UTC)

    assert not market_closed("binance", saturday)


def test_gold_is_closed_from_friday_evening_to_sunday_evening() -> None:
    assert not market_closed("twelvedata", datetime(2026, 1, 9, 21, tzinfo=UTC))  # Fri 21:00
    assert market_closed("twelvedata", datetime(2026, 1, 9, 22, tzinfo=UTC))  # Fri 22:00
    assert market_closed("twelvedata", datetime(2026, 1, 10, 12, tzinfo=UTC))  # Saturday
    assert market_closed("twelvedata", datetime(2026, 1, 11, 21, tzinfo=UTC))  # Sun 21:00
    assert not market_closed("twelvedata", datetime(2026, 1, 11, 22, tzinfo=UTC))  # Sun 22:00


def test_no_gaps_when_every_candle_exists() -> None:
    have = _hours(MON, 24)

    assert find_gaps(have, "binance", Timeframe.H1, MON, MON + HOUR * 24) == []


def test_a_missing_run_is_reported_once() -> None:
    have = [ts for ts in _hours(MON, 24) if not (5 <= ts.hour <= 7)]

    gaps = find_gaps(have, "binance", Timeframe.H1, MON, MON + HOUR * 24)

    assert gaps == [Gap(MON + HOUR * 5, MON + HOUR * 7, 3)]


def test_separate_holes_are_separate_gaps() -> None:
    have = [ts for ts in _hours(MON, 24) if ts.hour not in (3, 10, 11)]

    gaps = find_gaps(have, "binance", Timeframe.H1, MON, MON + HOUR * 24)

    assert [(g.start.hour, g.count) for g in gaps] == [(3, 1), (10, 2)]


def test_the_gold_weekend_is_not_a_gap() -> None:
    friday = datetime(2026, 1, 9, tzinfo=UTC)
    # Friday candles up to 21:00, then nothing until Sunday 22:00, then Sunday 22:00-23:00.
    have = _hours(friday, 22) + _hours(datetime(2026, 1, 11, 22, tzinfo=UTC), 2)

    gaps = find_gaps(have, "twelvedata", Timeframe.H1, friday, datetime(2026, 1, 12, tzinfo=UTC))

    assert gaps == []


def test_the_same_weekend_is_a_gap_for_crypto() -> None:
    friday = datetime(2026, 1, 9, tzinfo=UTC)
    have = _hours(friday, 22)

    gaps = find_gaps(have, "binance", Timeframe.H1, friday, datetime(2026, 1, 10, tzinfo=UTC))

    assert gaps == [Gap(friday + HOUR * 22, friday + HOUR * 23, 2)]


def test_a_misaligned_start_is_rounded_up_to_the_candle_grid() -> None:
    gaps = find_gaps([], "binance", Timeframe.H1, MON + timedelta(minutes=10), MON + HOUR * 3)

    assert gaps == [Gap(MON + HOUR, MON + HOUR * 2, 2)]


def test_daily_candles() -> None:
    days = [MON + timedelta(days=i) for i in (0, 1, 3)]

    gaps = find_gaps(days, "binance", Timeframe.D1, MON, MON + timedelta(days=4))

    assert gaps == [Gap(MON + timedelta(days=2), MON + timedelta(days=2), 1)]


def test_gold_weekend_follows_new_york_time_in_summer() -> None:
    # In July New York is UTC-4, so the week closes Friday 21:00 UTC and reopens Sunday 21:00.
    assert not market_closed("twelvedata", datetime(2026, 7, 10, 20, tzinfo=UTC))
    assert market_closed("twelvedata", datetime(2026, 7, 10, 21, tzinfo=UTC))
    assert market_closed("twelvedata", datetime(2026, 7, 12, 20, tzinfo=UTC))
    assert not market_closed("twelvedata", datetime(2026, 7, 12, 21, tzinfo=UTC))
