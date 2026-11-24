"""Keep stored candles current: fetch what is new, then find and refill gaps."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.logging import get_logger
from app.data.adapters.base import MarketDataAdapter, RawCandle
from app.data.backfill import backfill
from app.data.gaps import Gap, find_gaps
from app.data.models import Candle, Timeframe
from app.data.repository import get_or_create_instrument, insert_candles, latest_candle_time
from app.data.universe import InstrumentSpec

logger = get_logger(__name__)

LOOKBACK_DAYS = 30


@dataclass(frozen=True, slots=True)
class UpdateResult:
    new: int
    gaps_found: int
    gaps_refilled: int


async def update_instrument(
    sessions: async_sessionmaker[AsyncSession],
    adapter: MarketDataAdapter,
    spec: InstrumentSpec,
    timeframe: Timeframe,
    *,
    now: datetime | None = None,
    lookback_days: int = LOOKBACK_DAYS,
) -> UpdateResult:
    """Pull candles since the latest stored one, then refill gaps in the last `lookback_days`."""
    now = now or datetime.now(UTC)
    window_start = now - timedelta(days=lookback_days)

    async with sessions() as session:
        instrument = await get_or_create_instrument(session, spec)
        await session.commit()
        instrument_id = instrument.id
        latest = await latest_candle_time(session, instrument_id, timeframe)

    async def sink(candles: list[RawCandle]) -> int:
        async with sessions() as session:
            return await insert_candles(session, instrument_id, timeframe, candles)

    start = latest + timedelta(seconds=timeframe.seconds) if latest else window_start
    new = await backfill(adapter, spec.symbol, timeframe, start, sink)

    gaps = await _gaps(sessions, instrument_id, spec, timeframe, window_start, now)
    refilled = 0
    if gaps:
        logger.warning(
            "candle_gaps_found",
            venue=spec.venue,
            symbol=spec.symbol,
            timeframe=timeframe.value,
            gaps=len(gaps),
            first=gaps[0].start.isoformat(),
            missing=sum(gap.count for gap in gaps),
        )
        new += await backfill(adapter, spec.symbol, timeframe, gaps[0].start, sink)
        refilled = len(gaps) - len(
            await _gaps(sessions, instrument_id, spec, timeframe, window_start, now)
        )
    return UpdateResult(new=new, gaps_found=len(gaps), gaps_refilled=refilled)


async def _gaps(
    sessions: async_sessionmaker[AsyncSession],
    instrument_id: int,
    spec: InstrumentSpec,
    timeframe: Timeframe,
    start: datetime,
    end: datetime,
) -> list[Gap]:
    async with sessions() as session:
        # Only look for holes inside the history we have; what came before is a backfill job.
        earliest = (
            await session.execute(
                select(func.min(Candle.ts)).where(
                    Candle.instrument_id == instrument_id, Candle.timeframe == timeframe.value
                )
            )
        ).scalar_one_or_none()
        if earliest is None:
            return []
        start = max(start, earliest)
        result = await session.execute(
            select(Candle.ts).where(
                Candle.instrument_id == instrument_id,
                Candle.timeframe == timeframe.value,
                Candle.ts >= start,
                Candle.ts < end,
            )
        )
        existing = list(result.scalars())
    return find_gaps(existing, spec.venue, timeframe, start, end)
