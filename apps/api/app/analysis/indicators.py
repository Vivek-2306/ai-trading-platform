"""Technical indicators on candle series, built on TA-Lib.

Every function takes and returns NumPy arrays of the same length as the input. The first
values of an indicator (its warm-up) are NaN, meaning "not available": they are never
filled with made-up numbers. Indicators are analysis only: they use floats, and nothing
that sizes or places an order should read them without converting through the risk engine.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import numpy as np
import talib
from numpy.typing import NDArray

from app.data.adapters.base import RawCandle

Array = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class CandleSeries:
    """Candles as parallel arrays, oldest first."""

    times: list[datetime]
    open: Array
    high: Array
    low: Array
    close: Array
    volume: Array
    # The newest close as the exact stored decimal (the arrays above are floats, for analysis).
    last_close: Decimal | None = None

    def __len__(self) -> int:
        return len(self.times)

    @classmethod
    def from_candles(cls, candles: list[RawCandle]) -> "CandleSeries":
        ordered = sorted(candles, key=lambda c: c.ts)
        return cls(
            times=[c.ts for c in ordered],
            open=np.array([float(c.open) for c in ordered], dtype=np.float64),
            high=np.array([float(c.high) for c in ordered], dtype=np.float64),
            low=np.array([float(c.low) for c in ordered], dtype=np.float64),
            close=np.array([float(c.close) for c in ordered], dtype=np.float64),
            volume=np.array([float(c.volume) for c in ordered], dtype=np.float64),
            last_close=ordered[-1].close if ordered else None,
        )

    def upto(self, end: int) -> "CandleSeries":
        """The first `end` candles (a view of the past as of that moment)."""
        return CandleSeries(
            self.times[:end],
            self.open[:end],
            self.high[:end],
            self.low[:end],
            self.close[:end],
            self.volume[:end],
            self.last_close if end >= len(self) else Decimal(str(self.close[end - 1])),
        )


def sma(close: Array, period: int = 20) -> Array:
    return np.asarray(talib.SMA(close, timeperiod=period), dtype=np.float64)


def ema(close: Array, period: int = 20) -> Array:
    return np.asarray(talib.EMA(close, timeperiod=period), dtype=np.float64)


def rsi(close: Array, period: int = 14) -> Array:
    """Wilder's RSI, 0 to 100."""
    return np.asarray(talib.RSI(close, timeperiod=period), dtype=np.float64)


def macd(
    close: Array, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[Array, Array, Array]:
    """(MACD line, signal line, histogram)."""
    line, sig, hist = talib.MACD(close, fastperiod=fast, slowperiod=slow, signalperiod=signal)
    return (
        np.asarray(line, dtype=np.float64),
        np.asarray(sig, dtype=np.float64),
        np.asarray(hist, dtype=np.float64),
    )


def atr(high: Array, low: Array, close: Array, period: int = 14) -> Array:
    """Wilder's average true range, in price units."""
    return np.asarray(talib.ATR(high, low, close, timeperiod=period), dtype=np.float64)


def bollinger(
    close: Array, period: int = 20, deviations: float = 2.0
) -> tuple[Array, Array, Array]:
    """(upper, middle, lower) bands: a simple average and population standard deviation."""
    upper, middle, lower = talib.BBANDS(
        close,
        timeperiod=period,
        nbdevup=deviations,
        nbdevdn=deviations,
        matype=0,  # type: ignore[arg-type]  # 0 = simple average
    )
    return (
        np.asarray(upper, dtype=np.float64),
        np.asarray(middle, dtype=np.float64),
        np.asarray(lower, dtype=np.float64),
    )


def vwap(high: Array, low: Array, close: Array, volume: Array, period: int = 20) -> Array:
    """Rolling volume-weighted average price of the typical price (high+low+close)/3 over
    the last `period` candles. NaN where the window is incomplete or has no volume (spot gold
    from Twelve Data has none)."""
    typical = (high + low + close) / 3.0
    out = np.full(len(close), np.nan, dtype=np.float64)
    if len(close) < period:
        return out
    weighted = np.convolve(typical * volume, np.ones(period), mode="valid")
    total = np.convolve(volume, np.ones(period), mode="valid")
    with np.errstate(divide="ignore", invalid="ignore"):
        values = np.where(total > 0, weighted / total, np.nan)
    out[period - 1 :] = values
    return out
