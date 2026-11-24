"""Reading and writing market data."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.adapters.base import RawCandle
from app.data.models import Candle, Instrument, Timeframe
from app.data.universe import InstrumentSpec

# 8 columns per row; asyncpg allows 32,767 bind parameters per statement.
_WRITE_CHUNK = 2000


async def get_or_create_instrument(session: AsyncSession, spec: InstrumentSpec) -> Instrument:
    statement = (
        insert(Instrument)
        .values(venue=spec.venue, symbol=spec.symbol, asset_class=spec.asset_class.value)
        .on_conflict_do_nothing(constraint="uq_instruments_venue_symbol")
    )
    await session.execute(statement)
    result = await session.execute(
        select(Instrument).where(Instrument.venue == spec.venue, Instrument.symbol == spec.symbol)
    )
    return result.scalar_one()


async def insert_candles(
    session: AsyncSession, instrument_id: int, timeframe: Timeframe, candles: Sequence[RawCandle]
) -> int:
    """Store candles, skipping ones already present. Returns how many were new."""
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
        result = await session.execute(insert(Candle).values(rows).on_conflict_do_nothing())
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
