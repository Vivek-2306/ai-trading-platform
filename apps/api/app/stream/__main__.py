"""Run the stream service: `python -m app.stream` (from apps/api, needs Redis)."""

import asyncio
import signal

import ccxt.pro as ccxtpro

from app.core.config import get_settings
from app.core.error_reporting import init_error_reporting
from app.core.logging import configure_logging, get_logger
from app.core.redis import create_redis
from app.data.universe import default_universe
from app.stream.health import beat
from app.stream.service import Rows, StreamService

logger = get_logger(__name__)


async def run() -> None:
    settings = get_settings()
    configure_logging(settings)
    init_error_reporting(settings)
    redis = create_redis(settings)
    exchange = ccxtpro.binance({"enableRateLimit": True})
    symbols = [
        s.symbol for s in default_universe(twelve_data_enabled=False) if s.venue == "binance"
    ]

    async def handle(symbol: str, rows: Rows) -> None:
        logger.debug("stream_update", symbol=symbol, rows=len(rows))

    service = StreamService(exchange, symbols, handle, on_alive=lambda: beat(redis))
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, service.stop)
    try:
        await service.run()
    finally:
        await exchange.close()
        await redis.aclose()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
