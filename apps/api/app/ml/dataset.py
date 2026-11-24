"""Features and labels for the model.

Features are scale-free (ratios and percentages) built from the causal feature table, plus a few
past returns, so a model trained on one price level can be applied to another. The row at
candle t uses candles up to t only.

Label for row t, mirroring what the backtest does: a decision after candle t fills at the OPEN
of candle t+1, with the stop at 1.0 ATR(t) under the fill and the target at 1.6 ATR(t) over it.
Walk the next HORIZON candles: the stop is checked first (a candle that touches both counts as
a stop), then the target (the candle's high must trade THROUGH it). Label 1 = target first,
0 = stop first or neither within the horizon. Rows whose horizon is not fully known (the end of
the data) are NOT labelled and are dropped; this is also what keeps a label from reaching into
the locked out-of-sample period, because the builder is only ever given the tuning candles.
"""

from dataclasses import dataclass

import numpy as np

from app.analysis.features import FeatureTable, compute_features
from app.analysis.indicators import Array, CandleSeries

STOP_ATR = 1.0
TARGET_ATR = 1.6
HORIZON = 24  # candles; a trade not resolved by then counts as a loss of the setup (label 0)
RETURN_LAGS = (1, 3, 10)

FEATURE_NAMES = (
    "close_vs_sma_fast",
    "close_vs_sma_slow",
    "sma_trend",
    "ema_trend",
    "rsi",
    "macd_hist_pct",
    "atr_percent",
    "percent_b",
    "close_vs_vwap",
    "ret_1",
    "ret_3",
    "ret_10",
)


@dataclass(frozen=True, slots=True)
class Dataset:
    """Rows are candle indices `index`; `x` has one column per FEATURE_NAMES entry."""

    index: np.ndarray  # candle index of each row, ascending
    x: np.ndarray  # shape (rows, len(FEATURE_NAMES))
    y: np.ndarray  # 0 or 1
    label_end: np.ndarray  # last candle index each label looked at (for purging)

    def __len__(self) -> int:
        return len(self.index)


def _ratio(a: Array, b: Array, minus_one: bool = True) -> Array:
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(b != 0, a / b - (1.0 if minus_one else 0.0), np.nan)
    return np.asarray(out, dtype=np.float64)


def feature_matrix(series: CandleSeries, table: FeatureTable | None = None) -> np.ndarray:
    """(n, len(FEATURE_NAMES)); NaN where a feature is not available yet. Causal."""
    f = table if table is not None else compute_features(series)
    close = series.close
    cols: dict[str, Array] = {
        "close_vs_sma_fast": _ratio(close, f["sma_fast"]),
        "close_vs_sma_slow": _ratio(close, f["sma_slow"]),
        "sma_trend": _ratio(f["sma_fast"], f["sma_slow"]),
        "ema_trend": _ratio(f["ema_fast"], f["ema_slow"]),
        "rsi": f["rsi"],
        "macd_hist_pct": _ratio(f["macd_hist"], close, minus_one=False) * 100.0,
        "atr_percent": f["atr_percent"],
        "percent_b": f["percent_b"],
        "close_vs_vwap": _ratio(close, f["vwap"]),
    }
    for lag in RETURN_LAGS:
        shifted = np.full(len(close), np.nan, dtype=np.float64)
        shifted[lag:] = close[:-lag] if lag < len(close) else shifted[lag:]
        cols[f"ret_{lag}"] = _ratio(close, shifted)
    return np.column_stack([cols[name] for name in FEATURE_NAMES])


def label_trade(series: CandleSeries, t: int, atr: float, horizon: int = HORIZON) -> int | None:
    """1 if the target is hit before the stop within `horizon` candles of the fill at t+1's
    open, 0 otherwise; None if the horizon is not fully available."""
    if t + horizon >= len(series) or not np.isfinite(atr) or atr <= 0:
        return None
    fill = series.open[t + 1]
    stop, target = fill - STOP_ATR * atr, fill + TARGET_ATR * atr
    for i in range(t + 1, t + 1 + horizon):
        if series.low[i] <= stop:
            return 0
        if series.high[i] > target:
            return 1
    return 0


def build_dataset(series: CandleSeries, horizon: int = HORIZON) -> Dataset:
    """Every candle with all features available and a fully known label."""
    table = compute_features(series)
    x_all = feature_matrix(series, table)
    atr = table["atr"]
    rows, labels, ends = [], [], []
    for t in range(len(series)):
        if not np.isfinite(x_all[t]).all():
            continue
        label = label_trade(series, t, float(atr[t]), horizon)
        if label is None:
            continue
        rows.append(t)
        labels.append(label)
        ends.append(t + horizon)
    index = np.array(rows, dtype=np.int64)
    return Dataset(
        index=index,
        x=x_all[index] if len(index) else np.empty((0, len(FEATURE_NAMES))),
        y=np.array(labels, dtype=np.int8),
        label_end=np.array(ends, dtype=np.int64),
    )
