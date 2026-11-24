"""The no-look-ahead guarantee for features, plus the shape of the feature table."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np

from app.analysis.features import MIN_CANDLES, compute_features, find_lookahead, latest
from app.analysis.indicators import CandleSeries
from app.data.adapters.base import RawCandle


def _series(count: int, step: timedelta = timedelta(hours=1), seed: int = 3) -> CandleSeries:
    rng = np.random.default_rng(seed)
    close = np.cumsum(rng.normal(0, 1, count)) + 200
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = [
        RawCandle(
            start + step * i,
            Decimal(str(round(c, 4))),
            Decimal(str(round(c + abs(rng.normal(0.5, 0.2)), 4))),
            Decimal(str(round(c - abs(rng.normal(0.5, 0.2)), 4))),
            Decimal(str(round(c + rng.normal(0, 0.2), 4))),
            Decimal(str(round(rng.uniform(1, 9), 3))),
        )
        for i, c in enumerate(close)
    ]
    return CandleSeries.from_candles(candles)


def test_features_have_one_value_per_candle() -> None:
    series = _series(150)

    table = compute_features(series)

    assert all(len(values) == 150 for values in table.values())
    assert {"rsi", "macd", "atr", "bb_upper", "vwap", "percent_b", "sma_slow"} <= set(table)


def test_nothing_is_available_before_the_warm_up_ends_and_everything_after() -> None:
    table = compute_features(_series(150))

    for name, values in table.items():
        if name == "close":
            continue
        assert np.isnan(values[:10]).all(), name
        assert not np.isnan(values[MIN_CANDLES + 5 :]).any(), name


def test_no_feature_at_time_t_uses_a_later_candle() -> None:
    series = _series(160)

    assert find_lookahead(compute_features, series) == []


def test_the_lookahead_check_catches_a_leaky_feature() -> None:
    def leaky(series: CandleSeries) -> dict[str, np.ndarray]:
        table = compute_features(series)
        # "Tomorrow's close": the value at t is the close at t+1. This is exactly the bug
        # the check exists for.
        table["tomorrow_close"] = np.append(series.close[1:], np.nan)
        return table

    found = find_lookahead(leaky, _series(80), checkpoints=[30, 40, 50])

    assert {f.feature for f in found} == {"tomorrow_close"}
    assert [f.index for f in found] == [30, 40, 50]


def test_works_for_any_timeframe_spacing() -> None:
    for step in (timedelta(minutes=1), timedelta(minutes=5), timedelta(days=1)):
        series = _series(120, step)
        assert find_lookahead(compute_features, series, checkpoints=[60, 90, 119]) == []


def test_latest_reports_none_for_features_still_warming_up() -> None:
    short = latest(compute_features(_series(10)))
    full = latest(compute_features(_series(150)))

    assert short["rsi"] is None and short["sma_slow"] is None
    assert short["close"] is not None
    assert all(value is not None for value in full.values())
    assert 0 <= (full["rsi"] or -1) <= 100


def test_changing_a_future_candle_does_not_change_past_features() -> None:
    series = _series(120)
    base = compute_features(series)
    altered_close = series.close.copy()
    altered_close[100:] += 50  # a big move at the end
    altered = CandleSeries(
        series.times, series.open, series.high, series.low, altered_close, series.volume
    )

    changed = compute_features(altered)

    for name in ("rsi", "sma_fast", "ema_fast", "macd"):
        assert np.allclose(base[name][:100], changed[name][:100], equal_nan=True), name
