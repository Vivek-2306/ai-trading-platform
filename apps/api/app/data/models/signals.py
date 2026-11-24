"""Trading signals. The table is append-only: the database refuses UPDATE, DELETE and TRUNCATE,
so every signal ever produced stays on record exactly as it was shown."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.data.base import Base


class SignalAction(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    NO_TRADE = "NO_TRADE"


class Signal(Base):
    """One decision about one instrument and timeframe, made when a candle closed."""

    __tablename__ = "signals"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id", "timeframe", "candle_ts", "rule_version", name="uq_signals_candle"
        ),
        CheckConstraint("action IN ('BUY', 'SELL', 'HOLD', 'NO_TRADE')", name="action_known"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_in_range"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="RESTRICT"), index=True
    )
    timeframe: Mapped[str] = mapped_column(String(4))
    # Open time of the candle this signal is about (the last closed candle at decision time).
    candle_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    action: Mapped[str] = mapped_column(String(8))
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    # [{"code": "rsi_oversold", "text": "...", "direction": "buy"}, ...]
    reasons: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    # The feature values the decision was based on, for audit.
    inputs: Mapped[dict[str, Any]] = mapped_column(JSONB)
    rule_version: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
