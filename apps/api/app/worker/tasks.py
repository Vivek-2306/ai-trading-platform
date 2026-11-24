"""Background tasks. Real jobs (data pulls, analysis, backtests) arrive in feature phases."""

import asyncio
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.logging import get_logger
from app.data.adapters.base import RawCandle
from app.data.adapters.factory import build_adapter
from app.data.backfill import backfill, years_ago
from app.data.models import AssetClass, Timeframe
from app.data.repository import get_or_create_instrument, insert_candles
from app.data.retention import delete_old_minute_candles
from app.data.universe import InstrumentSpec, default_universe
from app.data.update import update_instrument
from app.worker.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="app.worker.tasks.ping")
def ping() -> str:
    """Round-trip check: a worker is consuming the queue."""
    return "pong"


# ignore_result: nothing reads it, and storing one per minute would fill the result backend.
@celery_app.task(name="app.worker.tasks.heartbeat", ignore_result=True)
def heartbeat() -> str:
    """Scheduled by beat; proves beat and a worker are both alive. Logs only."""
    now = datetime.now(UTC).isoformat()
    logger.info("worker_heartbeat", at=now)
    return now


async def _backfill(venue: str, symbol: str, asset_class: str, timeframe: str, years: float) -> int:
    settings = get_settings()
    adapter = build_adapter(venue, settings)
    # One short-lived engine per run: Celery tasks do not share an event loop.
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    tf = Timeframe(timeframe)
    try:
        async with sessions() as session:
            spec = InstrumentSpec(venue, symbol, AssetClass(asset_class))
            instrument = await get_or_create_instrument(session, spec)
            await session.commit()
            instrument_id = instrument.id

        async def sink(candles: list[RawCandle]) -> int:
            async with sessions() as session:
                return await insert_candles(session, instrument_id, tf, candles, overwrite=True)

        return await backfill(adapter, symbol, tf, years_ago(years), sink)
    finally:
        await adapter.aclose()
        await engine.dispose()


# Safe to run twice (acks_late can redeliver): existing candles are skipped.
@celery_app.task(name="app.worker.tasks.backfill_candles")
def backfill_candles(
    venue: str, symbol: str, asset_class: str, timeframe: str, years: float
) -> int:
    """Load `years` of history for one instrument and timeframe. Returns new candles stored."""
    return asyncio.run(_backfill(venue, symbol, asset_class, timeframe, years))


UPDATE_TIMEFRAMES = (Timeframe.H1, Timeframe.D1)


async def _update_all() -> dict[str, int]:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    new_by_instrument: dict[str, int] = {}
    try:
        for spec in default_universe(twelve_data_enabled=settings.twelve_data_api_key is not None):
            adapter = build_adapter(spec.venue, settings)
            try:
                for timeframe in UPDATE_TIMEFRAMES:
                    key = f"{spec.venue}:{spec.symbol}:{timeframe.value}"
                    try:
                        result = await update_instrument(sessions, adapter, spec, timeframe)
                    except Exception:
                        # One failing instrument must not stop the others.
                        logger.exception("candle_update_failed", instrument=key)
                        continue
                    new_by_instrument[key] = result.new
            finally:
                await adapter.aclose()
    finally:
        await engine.dispose()
    return new_by_instrument


# Safe to run twice: candles already stored are skipped.
@celery_app.task(name="app.worker.tasks.update_candles", ignore_result=True)
def update_candles() -> dict[str, int]:
    """Fetch new candles for every tracked instrument and refill recent gaps."""
    return asyncio.run(_update_all())


async def _retention() -> int:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        return await delete_old_minute_candles(sessions, settings.candle_1m_retention_days)
    finally:
        await engine.dispose()


@celery_app.task(name="app.worker.tasks.apply_candle_retention", ignore_result=True)
def apply_candle_retention() -> int:
    """Delete 1m candles older than CANDLE_1M_RETENTION_DAYS. Safe to run twice."""
    return asyncio.run(_retention())
