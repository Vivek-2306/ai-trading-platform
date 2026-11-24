"""Three scalping strategies, rules only, with every parameter fixed in advance.

The parameters below were chosen BEFORE looking at any backtest result and are not tuned: if
they were adjusted after seeing results, the locked out-of-sample period would no longer be a
fair test. A strategy is a pure function of features computed from candles up to now (the
look-ahead check in the tests proves that), returning BUY, SELL or HOLD with an ATR for the
risk engine to place the stop and target. Scalping is judged net of costs, and the research
question is honest: does any of this survive them?

- EMA cross: 9 over 21 exponential averages; buy the cross up, exit on the cross down.
- VWAP pullback: in an uptrend (21 over 50), price dips under the volume-weighted average of
  the last hour-ish and closes back above it while rising; exit when it loses VWAP in a downtrend.
- Range breakout: close above the highest high of the previous 20 candles on at least 1.5x
  normal volume; exit on a close under the lowest low of the previous 10.
"""

from decimal import Decimal

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from app.analysis import indicators as ind
from app.analysis.features import FeatureTable
from app.analysis.indicators import Array, CandleSeries
from app.data.models import SignalAction
from app.signals.rules import Decision, Reason

# Fixed up front. Do not tune.
EMA_FAST, EMA_SLOW, EMA_TREND = 9, 21, 50
VWAP_WINDOW = 60
BREAKOUT_HIGH, BREAKOUT_EXIT_LOW, VOLUME_WINDOW, VOLUME_RATIO = 20, 10, 20, 1.5
PULLBACK_LOOKBACK = 3
ATR_PERIOD = 14

NAN = float("nan")


def _prior_extreme(values: Array, window: int, fn: str) -> Array:
    """max or min over the PREVIOUS `window` values (not including the current one)."""
    out = np.full(len(values), np.nan, dtype=np.float64)
    if len(values) > window:
        view = sliding_window_view(values, window)[:-1]  # windows ending one candle before t
        out[window:] = view.max(axis=1) if fn == "max" else view.min(axis=1)
    return out


def scalp_features(series: CandleSeries) -> FeatureTable:
    """Causal features: the value at t uses candles up to t only."""
    close, high, low, volume = series.close, series.high, series.low, series.volume
    atr = ind.atr(high, low, close, ATR_PERIOD)
    with np.errstate(divide="ignore", invalid="ignore"):
        atr_percent = np.where(close > 0, atr / close * 100.0, np.nan)
    mean_volume = np.full(len(volume), np.nan, dtype=np.float64)
    if len(volume) > VOLUME_WINDOW:
        mean_volume[VOLUME_WINDOW:] = sliding_window_view(volume, VOLUME_WINDOW)[:-1].mean(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        volume_ratio = np.where(mean_volume > 0, volume / mean_volume, np.nan)
    return {
        "close": close,
        "ema_fast": ind.ema(close, EMA_FAST),
        "ema_slow": ind.ema(close, EMA_SLOW),
        "ema_trend": ind.ema(close, EMA_TREND),
        "vwap": ind.vwap(high, low, close, volume, VWAP_WINDOW),
        "atr": atr,
        "atr_percent": np.asarray(atr_percent, dtype=np.float64),
        "breakout_high": _prior_extreme(high, BREAKOUT_HIGH, "max"),
        "exit_low": _prior_extreme(low, BREAKOUT_EXIT_LOW, "min"),
        "volume_ratio": np.asarray(volume_ratio, dtype=np.float64),
    }


def _now(table: FeatureTable, name: str, back: int = 0) -> float:
    values = table[name]
    index = len(values) - 1 - back
    return float(values[index]) if index >= 0 else NAN


def _decide(action: SignalAction, code: str, text: str, atr: float) -> Decision:
    direction = {"BUY": "buy", "SELL": "sell"}.get(action.value, "neutral")
    return Decision(
        action,
        Decimal("0.6"),
        [Reason(code, text, direction, 1.0)],
        {"atr": atr},
    )


def _hold(atr: float) -> Decision:
    return _decide(SignalAction.HOLD, "no_setup", "No setup.", atr)


def ema_cross(table: FeatureTable) -> Decision:
    fast, slow = _now(table, "ema_fast"), _now(table, "ema_slow")
    fast_before, slow_before = _now(table, "ema_fast", 1), _now(table, "ema_slow", 1)
    atr = _now(table, "atr")
    if np.isnan([fast, slow, fast_before, slow_before, atr]).any():
        return _hold(atr)
    if fast_before <= slow_before and fast > slow:
        return _decide(
            SignalAction.BUY, "ema_cross_up", "The fast average crossed above the slow one.", atr
        )
    if fast_before >= slow_before and fast < slow:
        return _decide(
            SignalAction.SELL, "ema_cross_down", "The fast average crossed below the slow one.", atr
        )
    return _hold(atr)


def vwap_pullback(table: FeatureTable) -> Decision:
    close, vwap = _now(table, "close"), _now(table, "vwap")
    close_before = _now(table, "close", 1)
    trend, slow, fast = _now(table, "ema_slow"), _now(table, "ema_trend"), _now(table, "ema_fast")
    atr = _now(table, "atr")
    if np.isnan([close, vwap, close_before, trend, slow, fast, atr]).any():
        return _hold(atr)
    uptrend = trend > slow
    dipped = any(
        _now(table, "close", back) < _now(table, "vwap", back)
        for back in range(1, PULLBACK_LOOKBACK + 1)
        if not np.isnan(_now(table, "vwap", back))
    )
    if uptrend and dipped and close > vwap and close > close_before:
        return _decide(
            SignalAction.BUY,
            "vwap_reclaim",
            "Price dipped under VWAP and closed back above it in an uptrend.",
            atr,
        )
    if close < vwap and fast < trend:
        return _decide(
            SignalAction.SELL,
            "vwap_lost",
            "Price is under VWAP with the short average under the medium one.",
            atr,
        )
    return _hold(atr)


def range_breakout(table: FeatureTable) -> Decision:
    close = _now(table, "close")
    high, low = _now(table, "breakout_high"), _now(table, "exit_low")
    volume_ratio, atr = _now(table, "volume_ratio"), _now(table, "atr")
    if np.isnan([close, high, low, volume_ratio, atr]).any():
        return _hold(atr)
    if close > high and volume_ratio >= VOLUME_RATIO:
        return _decide(
            SignalAction.BUY, "breakout", "Closed above the 20-candle high on heavy volume.", atr
        )
    if close < low:
        return _decide(SignalAction.SELL, "range_lost", "Closed under the 10-candle low.", atr)
    return _hold(atr)
