"""Run the stream service: `python -m app.stream` (from apps/api, needs Redis and the database)."""

import asyncio
import signal
from datetime import UTC, datetime, timedelta

import ccxt.pro as ccxtpro
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.error_reporting import init_error_reporting
from app.core.logging import configure_logging, get_logger
from app.core.redis import create_redis
from app.data.adapters.base import RawCandle
from app.data.adapters.binance import BinanceAdapter
from app.data.aggregates import refresh_aggregates
from app.data.backfill import backfill
from app.data.models import Timeframe
from app.data.repository import get_or_create_instrument, insert_candles
from app.data.universe import default_universe
from app.data.update import update_instrument
from app.stream.healer import GapHealer
from app.stream.health import beat
from app.stream.service import StreamService
from app.stream.writer import CandleWriter

logger = get_logger(__name__)

HEAL_LOOKBACK_DAYS = 1
RECHECK_MINUTES = 10
HEAL_REFRESH_DAYS = 30


async def run() -> None:
    settings = get_settings()
    configure_logging(settings)
    init_error_reporting(settings)
    redis = create_redis(settings)
    exchange = ccxtpro.binance({"enableRateLimit": True})
    engine = create_async_engine(settings.database_url, pool_size=2)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    specs = [s for s in default_universe(twelve_data_enabled=False) if s.venue == "binance"]
    instrument_ids: dict[str, int] = {}
    async with sessions() as session:
        for spec in specs:
            instrument_ids[spec.symbol] = (await get_or_create_instrument(session, spec)).id
        await session.commit()

    async def persist(symbol: str, candles: list[RawCandle]) -> int:
        async with sessions() as session:
            return await insert_candles(session, instrument_ids[symbol], Timeframe.M1, candles)

    writer = CandleWriter(redis, persist)
    rest = BinanceAdapter()

    async def rest_sink(spec_id: int, candles: list[RawCandle]) -> int:
        async with sessions() as session:
            return await insert_candles(session, spec_id, Timeframe.M1, candles, overwrite=True)

    async def heal() -> None:
        """Repair the last day over REST (authoritative): fill holes, and re-check the newest
        minutes, which the stream may have stored before their final values arrived."""
        changed = 0
        for spec in specs:
            try:
                result = await update_instrument(
                    sessions, rest, spec, Timeframe.M1, lookback_days=HEAL_LOOKBACK_DAYS
                )

                async def sink(
                    candles: list[RawCandle], sid: int = instrument_ids[spec.symbol]
                ) -> int:
                    return await rest_sink(sid, candles)

                recheck = await backfill(
                    rest,
                    spec.symbol,
                    Timeframe.M1,
                    datetime.now(UTC) - timedelta(minutes=RECHECK_MINUTES),
                    sink,
                )
                changed += result.new + recheck
                logger.info(
                    "stream_gap_heal",
                    symbol=spec.symbol,
                    new=result.new,
                    corrected=recheck,
                    gaps_found=result.gaps_found,
                    gaps_refilled=result.gaps_refilled,
                )
            except Exception:
                # One failing instrument must not stop the others from being healed.
                logger.exception("stream_gap_heal_failed", symbol=spec.symbol)
        if changed:
            await refresh_aggregates(engine, days=HEAL_REFRESH_DAYS)

    healer = GapHealer(heal)
    service = StreamService(
        exchange,
        list(instrument_ids),
        writer.handle,
        on_alive=lambda: beat(redis),
        on_reconnect=healer.request,
    )
    heal_task = asyncio.create_task(healer.run())
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, service.stop)
    try:
        await service.run()
    finally:
        heal_task.cancel()
        await asyncio.gather(heal_task, return_exceptions=True)
        await rest.aclose()
        await exchange.close()
        await redis.aclose()
        await engine.dispose()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
