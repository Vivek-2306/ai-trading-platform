"""The gap healer's scheduling, and the stream's reconnect signal."""

import asyncio
from typing import Any

import ccxt.async_support as ccxt

from app.stream.healer import GapHealer
from app.stream.service import Rows, StreamService


async def test_heals_at_start_on_request_and_survives_failures() -> None:
    calls = 0
    ran = asyncio.Event()

    async def heal() -> None:
        nonlocal calls
        calls += 1
        ran.set()
        if calls == 2:
            raise RuntimeError("REST is down")

    healer = GapHealer(heal, interval_seconds=3600)
    task = asyncio.create_task(healer.run())
    await asyncio.wait_for(ran.wait(), 1)
    assert calls == 1  # at startup

    for expected in (2, 3):  # a failing heal must not stop the next one
        ran.clear()
        healer.request()
        await asyncio.wait_for(ran.wait(), 1)
        assert calls == expected

    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


async def test_heals_again_after_the_interval() -> None:
    calls = 0
    done = asyncio.Event()

    async def heal() -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            done.set()

    task = asyncio.create_task(GapHealer(heal, interval_seconds=0.01).run())
    await asyncio.wait_for(done.wait(), 1)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


class Flaky:
    def __init__(self, script: list[Any]) -> None:
        self.script = script
        self.drained = asyncio.Event()

    async def watch_ohlcv(self, symbol: str, timeframe: str) -> Rows:
        if not self.script:
            self.drained.set()
            await asyncio.sleep(3600)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item  # type: ignore[no-any-return]


async def test_a_reconnect_asks_for_a_gap_check_but_a_first_connect_does_not() -> None:
    requests = 0

    def on_reconnect() -> None:
        nonlocal requests
        requests += 1

    async def noop(symbol: str, rows: Rows) -> None:
        return None

    async def fast_sleep(seconds: float) -> None:
        return None

    row: Rows = [[1.0, 1.0, 1.0, 1.0, 1.0, 1.0]]
    exchange = Flaky([row, row, ccxt.NetworkError("drop"), row, row])
    service = StreamService(
        exchange, ["BTC/USDT"], noop, on_reconnect=on_reconnect, sleep=fast_sleep
    )
    task = asyncio.create_task(service.run())
    await asyncio.wait_for(exchange.drained.wait(), 1)
    service.stop()
    await asyncio.wait_for(task, 1)

    assert requests == 1
