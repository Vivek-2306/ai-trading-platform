"""Refresh the 5m and 1h aggregates over a window.

The database refreshes them on a schedule, but only for the last couple of days. After a long
outage the heal job backfills older minutes, so it asks for a refresh of the whole window.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def refresh_aggregates(
    engine: AsyncEngine, days: int = 30, now: datetime | None = None
) -> None:
    end = (now or datetime.now(UTC)) + timedelta(hours=1)  # include the current bucket
    start = end - timedelta(days=days)
    # Timestamps come from our own clock, never from user input.
    window = f"'{start.strftime('%Y-%m-%d %H:%M:%S')}+00', '{end.strftime('%Y-%m-%d %H:%M:%S')}+00'"
    # CALL refresh_continuous_aggregate cannot run inside a transaction.
    async with engine.connect() as connection:
        auto = await connection.execution_options(isolation_level="AUTOCOMMIT")
        for view in ("candles_5m_agg", "candles_1h_agg"):
            await auto.execute(text(f"CALL refresh_continuous_aggregate('{view}', {window})"))
