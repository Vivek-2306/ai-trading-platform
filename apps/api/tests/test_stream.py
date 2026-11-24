"""Stream service behaviour with a scripted fake exchange. No network."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import ccxt.async_support as ccxt
import pytest
from structlog.testing import capture_logs

from app.stream.health import HEARTBEAT_KEY, beat, is_fresh
from app.stream.service import Rows, StreamService

ROWS: Rows = [[1795503600000.0, 1.0, 2.0, 0.5, 1.5, 10.0]]


class ScriptedExchange:
    """Each watch_ohlcv call pops the next scripted item: rows to return or an error to raise."""

    def __init__(self, script: list[Any], on_empty: asyncio.Event) -> None:
        self._script = script
        self._on_empty = on_empty

    async def watch_ohlcv(self, symbol: str, timeframe: str) -> Rows:
        if not self._script:
            self._on_empty.set()
            await asyncio.sleep(3600)  # idle until the service is stopped
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item  # type: ignore[no-any-return]


async def _run(
    script: list[Any], *, symbols: list[str] | None = None
) -> tuple[list[tuple[str, Rows]], list[float], int]:
    received: list[tuple[str, Rows]] = []
    sleeps: list[float] = []
    alive = 0
    drained = asyncio.Event()

    async def handler(symbol: str, rows: Rows) -> None:
        received.append((symbol, rows))

    async def on_alive() -> None:
        nonlocal alive
        alive += 1

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    service = StreamService(
        ScriptedExchange(script, drained),
        symbols or ["BTC/USDT"],
        handler,
        on_alive=on_alive,
        sleep=fake_sleep,
    )
    task = asyncio.create_task(service.run())
    await asyncio.wait_for(drained.wait(), timeout=2)
    service.stop()
    await asyncio.wait_for(task, timeout=2)  # stop() must end a watcher blocked on a quiet symbol
    return received, sleeps, alive


async def test_passes_updates_to_the_handler_and_signals_liveness() -> None:
    received, _, alive = await _run([ROWS, ROWS])

    assert received == [("BTC/USDT", ROWS), ("BTC/USDT", ROWS)]
    assert alive == 2


async def test_reconnects_with_growing_backoff_after_failures() -> None:
    script = [ccxt.NetworkError("drop"), ccxt.RequestTimeout("slow"), ccxt.NetworkError("x"), ROWS]

    received, sleeps, _ = await _run(script)

    assert sleeps == [1.0, 2.0, 4.0]
    assert received == [("BTC/USDT", ROWS)]


async def test_backoff_resets_after_a_good_message() -> None:
    script = [ccxt.NetworkError("a"), ccxt.NetworkError("b"), ROWS, ccxt.NetworkError("c"), ROWS]

    _, sleeps, _ = await _run(script)

    assert sleeps == [1.0, 2.0, 1.0]


async def test_backoff_is_capped() -> None:
    script: list[Any] = [ccxt.NetworkError("x")] * 8 + [ROWS]

    _, sleeps, _ = await _run(script)

    assert max(sleeps) == 30.0


async def test_a_disconnect_is_logged_without_details() -> None:
    with capture_logs() as logs:
        await _run([ccxt.NetworkError("secret url?key=abc"), ROWS])

    event = next(log for log in logs if log["event"] == "stream_disconnected")
    assert event["error"] == "NetworkError"
    assert "abc" not in str(event)


async def test_unexpected_errors_are_not_swallowed() -> None:
    drained = asyncio.Event()
    service = StreamService(
        ScriptedExchange([ValueError("bug")], drained), ["BTC/USDT"], handler=_noop_handler
    )

    with pytest.raises(ExceptionGroup) as info:
        await asyncio.wait_for(service.run(), timeout=2)

    assert info.group_contains(ValueError)


async def _noop_handler(symbol: str, rows: Rows) -> None:
    return None


class FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, tuple[str, int | None]] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.data[key] = (value, ex)


async def test_beat_writes_a_heartbeat_with_expiry() -> None:
    redis = FakeRedis()
    now = datetime(2026, 1, 1, tzinfo=UTC)

    await beat(redis, now)  # type: ignore[arg-type]

    assert redis.data[HEARTBEAT_KEY] == (now.isoformat(), 180)


def test_is_fresh() -> None:
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)

    assert is_fresh((now - timedelta(seconds=30)).isoformat(), now)
    assert not is_fresh((now - timedelta(seconds=300)).isoformat(), now)
    assert not is_fresh((now + timedelta(seconds=300)).isoformat(), now)  # from the future
    assert not is_fresh(None, now)
    assert not is_fresh("garbage", now)
