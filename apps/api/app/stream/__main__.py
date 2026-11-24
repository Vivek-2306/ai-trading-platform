"""Run the stream service: `python -m app.stream` (from apps/api, needs Redis and the database)."""

import asyncio
import signal

import ccxt.pro as ccxtpro
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.error_reporting import init_error_reporting
from app.core.logging import configure_logging, get_logger
from app.core.redis import create_redis
from app.data.adapters.base import RawCandle
from app.data.models import Timeframe
from app.data.repository import get_or_create_instrument, insert_candles
from app.data.universe import default_universe
from app.stream.health import beat
from app.stream.service import StreamService
from app.stream.writer import CandleWriter

logger = get_logger(__name__)


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
    service = StreamService(
        exchange, list(instrument_ids), writer.handle, on_alive=lambda: beat(redis)
    )
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, service.stop)
    try:
        await service.run()
    finally:
        await exchange.close()
        await redis.aclose()
        await engine.dispose()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
