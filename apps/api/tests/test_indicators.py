"""Indicators against independent reference implementations written the long way."""

import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np
import pytest

from app.analysis import indicators as ind
from app.data.adapters.base import RawCandle

RNG = np.random.default_rng(7)
N = 120
CLOSE = np.cumsum(RNG.normal(0, 1, N)) + 100.0
HIGH = CLOSE + RNG.uniform(0.1, 1.5, N)
LOW = CLOSE - RNG.uniform(0.1, 1.5, N)
VOLUME = RNG.uniform(1, 10, N)


def _close(a: float, b: float, tol: float = 1e-6) -> bool:
    return math.isclose(a, b, rel_tol=tol, abs_tol=tol)


def ref_sma(x: np.ndarray, p: int) -> list[float]:
    return [math.nan] * (p - 1) + [
        float(np.mean(x[i - p + 1 : i + 1])) for i in range(p - 1, len(x))
    ]


def ref_ema(x: np.ndarray, p: int) -> list[float]:
    k = 2 / (p + 1)
    out = [math.nan] * (p - 1)
    value = float(np.mean(x[:p]))  # seeded with the simple average of the first p values
    out.append(value)
    for price in x[p:]:
        value = price * k + value * (1 - k)
        out.append(value)
    return out


def ref_rsi(x: np.ndarray, p: int) -> list[float]:
    out = [math.nan] * p
    deltas = np.diff(x)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = gains[:p].mean()
    avg_loss = losses[:p].mean()
    out.append(100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss))
    for gain, loss in zip(gains[p:], losses[p:], strict=True):
        avg_gain = (avg_gain * (p - 1) + gain) / p
        avg_loss = (avg_loss * (p - 1) + loss) / p
        out.append(100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss))
    return out


def ref_atr(h: np.ndarray, low: np.ndarray, c: np.ndarray, p: int) -> list[float]:
    tr = [h[0] - low[0]] + [
        max(h[i] - low[i], abs(h[i] - c[i - 1]), abs(low[i] - c[i - 1])) for i in range(1, len(c))
    ]
    out = [math.nan] * p
    value = float(np.mean(tr[1 : p + 1]))  # TA-Lib skips the first bar's range
    out.append(value)
    for i in range(p + 1, len(c)):
        value = (value * (p - 1) + tr[i]) / p
        out.append(value)
    return out


def assert_same(actual: np.ndarray, expected: list[float]) -> None:
    assert len(actual) == len(expected)
    for a, e in zip(actual, expected, strict=True):
        if math.isnan(e):
            assert math.isnan(a), "warm-up values must be NaN"
        else:
            assert _close(float(a), e), (a, e)


def test_sma_matches_the_long_way() -> None:
    assert_same(ind.sma(CLOSE, 20), ref_sma(CLOSE, 20))


def test_ema_matches_the_long_way() -> None:
    assert_same(ind.ema(CLOSE, 12), ref_ema(CLOSE, 12))


def test_rsi_matches_wilders_method() -> None:
    assert_same(ind.rsi(CLOSE, 14), ref_rsi(CLOSE, 14))


def test_rsi_is_bounded_and_extremes_are_exact() -> None:
    rising = np.arange(1.0, 40.0)
    falling = np.arange(40.0, 1.0, -1.0)

    assert ind.rsi(rising, 14)[-1] == 100.0
    assert ind.rsi(falling, 14)[-1] == 0.0
    values = ind.rsi(CLOSE, 14)
    assert np.nanmin(values) >= 0 and np.nanmax(values) <= 100


def test_macd_is_the_difference_of_two_emas_and_the_histogram_is_line_minus_signal() -> None:
    line, signal, hist = ind.macd(CLOSE, 12, 26, 9)
    expected_line = np.array(ref_ema(CLOSE, 12)) - np.array(ref_ema(CLOSE, 26))

    # TA-Lib seeds the two EMAs at slightly different points than the long way, so the early
    # values differ a little; the influence of the seed fades and the series agree later on.
    assert np.allclose(line[100:], expected_line[100:], atol=5e-4)
    both = ~np.isnan(signal)
    assert np.allclose(hist[both], line[both] - signal[both], atol=1e-9)
    # TA-Lib reports nothing until all three outputs exist: slow period + signal period - 2.
    assert int(np.isnan(line).sum()) == 33
    assert int(np.isnan(signal).sum()) == 33


def test_atr_matches_wilders_method() -> None:
    assert_same(ind.atr(HIGH, LOW, CLOSE, 14), ref_atr(HIGH, LOW, CLOSE, 14))


def test_bollinger_bands() -> None:
    upper, middle, lower = ind.bollinger(CLOSE, 20, 2.0)
    for i in range(19, N):
        window = CLOSE[i - 19 : i + 1]
        std = float(np.std(window))  # population standard deviation, as TA-Lib does
        assert _close(float(middle[i]), float(np.mean(window)))
        assert _close(float(upper[i]), float(np.mean(window)) + 2 * std)
        assert _close(float(lower[i]), float(np.mean(window)) - 2 * std)
    assert np.isnan(upper[18])


def test_vwap_is_volume_weighted_and_nan_without_volume() -> None:
    result = ind.vwap(HIGH, LOW, CLOSE, VOLUME, period=5)
    i = 10
    typical = (HIGH + LOW + CLOSE) / 3
    expected = float(
        np.sum(typical[i - 4 : i + 1] * VOLUME[i - 4 : i + 1]) / np.sum(VOLUME[i - 4 : i + 1])
    )
    assert _close(float(result[i]), expected)
    assert np.isnan(result[3])  # the window is not full yet

    no_volume = ind.vwap(HIGH, LOW, CLOSE, np.zeros(N), period=5)
    assert np.isnan(no_volume).all()
    assert np.isnan(ind.vwap(HIGH[:3], LOW[:3], CLOSE[:3], VOLUME[:3], period=5)).all()


def test_short_input_is_all_warm_up_not_made_up_numbers() -> None:
    short = CLOSE[:5]

    for result in (ind.sma(short, 20), ind.ema(short, 20), ind.rsi(short, 14)):
        assert np.isnan(result).all()
        assert len(result) == 5


def test_series_from_candles_sorts_and_converts() -> None:
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    candles = [
        RawCandle(
            t0 + timedelta(hours=1),
            Decimal("2"),
            Decimal("3"),
            Decimal("1"),
            Decimal("2.5"),
            Decimal("4"),
        ),
        RawCandle(t0, Decimal("1"), Decimal("2"), Decimal("1"), Decimal("1.5"), Decimal("3")),
    ]

    series = ind.CandleSeries.from_candles(candles)

    assert series.times == [t0, t0 + timedelta(hours=1)]
    assert list(series.close) == [1.5, 2.5]
    assert len(series) == 2
    assert len(series.upto(1)) == 1 and list(series.upto(1).close) == [1.5]


@pytest.mark.parametrize("func", [ind.sma, ind.ema, ind.rsi])
def test_output_length_matches_input(func: object) -> None:
    assert len(func(CLOSE)) == N  # type: ignore[operator]
