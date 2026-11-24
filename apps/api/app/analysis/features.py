"""Features for signals and models: indicator values aligned to each candle.

The rule that matters: the feature at candle t may use candles up to and including t, and
nothing after it. All indicators here are causal, and `find_lookahead` proves it by
recomputing every feature from a truncated history and comparing.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

from app.analysis import indicators as ind
from app.analysis.indicators import Array, CandleSeries

FeatureTable = dict[str, Array]

# Windows are in candles, so the same code serves any timeframe.
SMA_FAST, SMA_SLOW = 20, 50
EMA_FAST, EMA_SLOW = 12, 26
RSI_PERIOD = 14
ATR_PERIOD = 14
BOLLINGER_PERIOD = 20
VWAP_PERIOD = 20
# Warm-up: candles needed before every feature has a value.
MIN_CANDLES = max(SMA_SLOW, EMA_SLOW + 9 - 1, BOLLINGER_PERIOD, VWAP_PERIOD, ATR_PERIOD + 1)


def compute_features(series: CandleSeries) -> FeatureTable:
    """One array per feature, the same length as the series. NaN means "not available yet"."""
    close = series.close
    macd_line, macd_signal, macd_hist = ind.macd(close)
    upper, middle, lower = ind.bollinger(close, BOLLINGER_PERIOD)
    atr = ind.atr(series.high, series.low, close, ATR_PERIOD)
    width = upper - lower
    with np.errstate(divide="ignore", invalid="ignore"):
        percent_b = np.where(width > 0, (close - lower) / width, np.nan)
        atr_percent = np.where(close > 0, atr / close * 100.0, np.nan)
    return {
        "close": close,
        "sma_fast": ind.sma(close, SMA_FAST),
        "sma_slow": ind.sma(close, SMA_SLOW),
        "ema_fast": ind.ema(close, EMA_FAST),
        "ema_slow": ind.ema(close, EMA_SLOW),
        "rsi": ind.rsi(close, RSI_PERIOD),
        "macd": macd_line,
        "macd_signal": macd_signal,
        "macd_hist": macd_hist,
        "atr": atr,
        "atr_percent": np.asarray(atr_percent, dtype=np.float64),
        "bb_upper": upper,
        "bb_middle": middle,
        "bb_lower": lower,
        "percent_b": np.asarray(percent_b, dtype=np.float64),
        "vwap": ind.vwap(series.high, series.low, close, series.volume, VWAP_PERIOD),
    }


def latest(table: FeatureTable) -> dict[str, float | None]:
    """The newest value of every feature; None where it is not available yet."""
    out: dict[str, float | None] = {}
    for name, values in table.items():
        value = float(values[-1]) if len(values) else float("nan")
        out[name] = value if np.isfinite(value) else None  # NaN and +-inf are "not available"
    return out


@dataclass(frozen=True, slots=True)
class Lookahead:
    feature: str
    index: int  # the candle whose value changed when later candles were removed


def find_lookahead(
    compute: Callable[[CandleSeries], FeatureTable],
    series: CandleSeries,
    checkpoints: Sequence[int] | None = None,
    tolerance: float = 1e-9,
) -> list[Lookahead]:
    """Features at candle t must not change when every candle after t is removed.

    For each checkpoint t, recompute on the first t+1 candles and compare the last row with
    the full-history row. Returns the features that differ (empty list = no look-ahead).
    """
    full = compute(series)
    points = list(checkpoints) if checkpoints is not None else list(range(len(series)))
    found: list[Lookahead] = []
    for t in points:
        truncated = compute(series.upto(t + 1))
        for name, values in full.items():
            before, after = float(truncated[name][t]), float(values[t])
            if np.isnan(before) and np.isnan(after):
                continue
            if np.isnan(before) != np.isnan(after) or abs(before - after) > tolerance * max(
                1.0, abs(after)
            ):
                found.append(Lookahead(name, t))
    return found
