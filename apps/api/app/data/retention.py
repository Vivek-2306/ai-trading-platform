"""Delete old 1-minute candles. Longer timeframes and the 5m/1h aggregates are kept."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.logging import get_logger
from app.data.models import Candle, Timeframe

logger = get_logger(__name__)


async def delete_old_minute_candles(
    sessions: async_sessionmaker[AsyncSession], days: int, now: datetime | None = None
) -> int:
    """Remove 1m candles opened more than `days` ago. 0 means keep everything."""
    if days <= 0:
        return 0
    cutoff = (now or datetime.now(UTC)) - timedelta(days=days)
    async with sessions() as session:
        result = await session.execute(
            delete(Candle).where(Candle.timeframe == Timeframe.M1.value, Candle.ts < cutoff)
        )
        await session.commit()
    deleted: int = result.rowcount  # type: ignore[attr-defined]
    logger.info("candle_retention_applied", days=days, deleted=deleted)
    return deleted
