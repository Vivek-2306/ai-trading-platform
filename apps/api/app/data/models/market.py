"""Market data tables: instruments and OHLCV candles.

Prices and volumes are NUMERIC (exact decimals), never floats. All times are UTC.
`candles` is a TimescaleDB hypertable partitioned on `ts`; the primary key
(instrument_id, timeframe, ts) means a candle can only exist once.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.data.base import Base

# 18 digits before the decimal point and 10 after covers crypto dust and large volumes.
PRICE = Numeric(28, 10)


class Timeframe(StrEnum):
    """Candle sizes. The value is what is stored in the database."""

    M1 = "1m"
    M5 = "5m"
    H1 = "1h"
    D1 = "1d"


class AssetClass(StrEnum):
    CRYPTO = "crypto"
    GOLD = "gold"


class Instrument(Base):
    """One tradable thing on one venue, e.g. BTC/USDT on Binance."""

    __tablename__ = "instruments"
    __table_args__ = (UniqueConstraint("venue", "symbol", name="uq_instruments_venue_symbol"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    venue: Mapped[str] = mapped_column(String(32))
    symbol: Mapped[str] = mapped_column(String(32))
    asset_class: Mapped[str] = mapped_column(String(16))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Candle(Base):
    """One OHLCV bar. `ts` is the bar's open time in UTC."""

    __tablename__ = "candles"
    __table_args__ = (
        CheckConstraint("high >= low", name="high_gte_low"),
        CheckConstraint("volume >= 0", name="volume_non_negative"),
        CheckConstraint("timeframe IN ('1m', '5m', '1h', '1d')", name="timeframe_known"),
    )

    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="RESTRICT"), primary_key=True
    )
    timeframe: Mapped[str] = mapped_column(String(4), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    open: Mapped[Decimal] = mapped_column(PRICE)
    high: Mapped[Decimal] = mapped_column(PRICE)
    low: Mapped[Decimal] = mapped_column(PRICE)
    close: Mapped[Decimal] = mapped_column(PRICE)
    volume: Mapped[Decimal] = mapped_column(PRICE)
