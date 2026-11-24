"""Reading and writing market data."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.adapters.base import RawCandle
from app.data.models import Candle, Instrument, Signal, Timeframe
from app.data.universe import InstrumentSpec

# 8 columns per row; asyncpg allows 32,767 bind parameters per statement.
_WRITE_CHUNK = 2000


async def get_or_create_instrument(session: AsyncSession, spec: InstrumentSpec) -> Instrument:
    where = (Instrument.venue == spec.venue, Instrument.symbol == spec.symbol)
    existing = (await session.execute(select(Instrument).where(*where))).scalar_one_or_none()
    if existing is not None:  # the usual case; avoids burning an id from the sequence
        return existing
    # Another worker may insert the same instrument at the same moment: ignore that race.
    await session.execute(
        insert(Instrument)
        .values(venue=spec.venue, symbol=spec.symbol, asset_class=spec.asset_class.value)
        .on_conflict_do_nothing(constraint="uq_instruments_venue_symbol")
    )
    return (await session.execute(select(Instrument).where(*where))).scalar_one()


async def insert_candles(
    session: AsyncSession,
    instrument_id: int,
    timeframe: Timeframe,
    candles: Sequence[RawCandle],
    *,
    overwrite: bool = False,
) -> int:
    """Store candles. Returns how many rows were written.

    By default candles already present are kept. With `overwrite=True` (used for REST data,
    which is authoritative) an existing candle whose values differ is corrected.
    """
    inserted = 0
    for start in range(0, len(candles), _WRITE_CHUNK):
        rows = [
            {
                "instrument_id": instrument_id,
                "timeframe": timeframe.value,
                "ts": candle.ts,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
            }
            for candle in candles[start : start + _WRITE_CHUNK]
        ]
        statement = insert(Candle).values(rows)
        if overwrite:
            changed = {c: statement.excluded[c] for c in ("open", "high", "low", "close", "volume")}
            statement = statement.on_conflict_do_update(
                index_elements=["instrument_id", "timeframe", "ts"],
                set_=changed,
                where=or_(*(getattr(Candle, c) != statement.excluded[c] for c in changed)),
            )
        else:
            statement = statement.on_conflict_do_nothing()
        result = await session.execute(statement)
        inserted += result.rowcount  # type: ignore[attr-defined]
    await session.commit()
    return inserted


async def latest_candle_time(
    session: AsyncSession, instrument_id: int, timeframe: Timeframe
) -> datetime | None:
    result = await session.execute(
        select(func.max(Candle.ts)).where(
            Candle.instrument_id == instrument_id, Candle.timeframe == timeframe.value
        )
    )
    return result.scalar_one_or_none()


async def record_signal(session: AsyncSession, signal: Signal) -> bool:
    """Append a signal. Returns False if one already exists for that instrument, timeframe,
    candle and rule version (so running a signal job twice stores it once)."""
    statement = (
        insert(Signal)
        .values(
            instrument_id=signal.instrument_id,
            timeframe=signal.timeframe,
            candle_ts=signal.candle_ts,
            action=signal.action,
            confidence=signal.confidence,
            reasons=signal.reasons,
            inputs=signal.inputs,
            rule_version=signal.rule_version,
        )
        .on_conflict_do_nothing(constraint="uq_signals_candle")
    )
    result = await session.execute(statement)
    await session.commit()
    return bool(result.rowcount)  # type: ignore[attr-defined]
