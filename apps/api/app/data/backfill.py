"""Load history for one instrument and timeframe, page by page.

Safe to run again: candles already stored are skipped, so a re-run only fills what is missing.
"""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from app.core.logging import get_logger
from app.data.adapters.base import MarketDataAdapter, RawCandle
from app.data.models import Timeframe

logger = get_logger(__name__)

PAGE_SIZE = 1000
MAX_PAGES = 10_000  # a runaway guard: 10 million candles

# Takes a page of candles, returns how many were new.
Sink = Callable[[list[RawCandle]], Awaitable[int]]


async def backfill(
    adapter: MarketDataAdapter,
    symbol: str,
    timeframe: Timeframe,
    start: datetime,
    sink: Sink,
    *,
    page_size: int = PAGE_SIZE,
) -> int:
    """Fetch candles from `start` until the source runs out. Returns the number of new candles."""
    since = start
    total_new = 0
    for page in range(1, MAX_PAGES + 1):
        candles = await adapter.fetch_candles(symbol, timeframe, since=since, limit=page_size)
        if not candles:
            break
        total_new += await sink(candles)
        logger.info(
            "backfill_progress",
            venue=adapter.venue,
            symbol=symbol,
            timeframe=timeframe.value,
            page=page,
            up_to=candles[-1].ts.isoformat(),
            new_total=total_new,
        )
        next_since = candles[-1].ts + timedelta(seconds=timeframe.seconds)
        if next_since <= since or len(candles) < page_size:
            break  # no progress, or a short page: we have caught up
        since = next_since
    logger.info(
        "backfill_done",
        venue=adapter.venue,
        symbol=symbol,
        timeframe=timeframe.value,
        new=total_new,
    )
    return total_new


def years_ago(years: float, now: datetime | None = None) -> datetime:
    return (now or datetime.now(UTC)) - timedelta(days=365.25 * years)
