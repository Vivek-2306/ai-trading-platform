"""Stored backtest runs (append-only) and the out-of-sample locks."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.data.base import Base


class BacktestRun(Base):
    """One backtest: what was run, on which data, and what came out."""

    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="RESTRICT"), index=True
    )
    timeframe: Mapped[str] = mapped_column(String(4))
    strategy: Mapped[str] = mapped_column(String(32))
    # "tuning" (the region you may tune on), "walk_forward" or "oos" (the locked period).
    segment: Mapped[str] = mapped_column(String(16))
    config: Mapped[dict[str, Any]] = mapped_column(JSONB)
    config_hash: Mapped[str] = mapped_column(String(16))
    range_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    range_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    candle_count: Mapped[int] = mapped_column(Integer)
    # sha256 of the candles used, to prove a re-run saw the same data.
    data_fingerprint: Mapped[str] = mapped_column(String(64))
    code_version: Mapped[str] = mapped_column(String(40))
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB)
    benchmark: Mapped[dict[str, Any]] = mapped_column(JSONB)
    trades: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    equity: Mapped[dict[str, Any]] = mapped_column(JSONB)  # downsampled curves for the chart
    details: Mapped[dict[str, Any]] = mapped_column(JSONB)  # stats, walk-forward windows, notes


class OosLock(Base):
    """Where the locked out-of-sample period starts, and the one configuration judged on it."""

    __tablename__ = "oos_locks"
    __table_args__ = (PrimaryKeyConstraint("symbol", "timeframe", "strategy", name="pk_oos_locks"),)

    symbol: Mapped[str] = mapped_column(String(32))
    timeframe: Mapped[str] = mapped_column(String(4))
    strategy: Mapped[str] = mapped_column(String(32))
    oos_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    config_hash: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
