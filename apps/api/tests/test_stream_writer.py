"""The writer decides what goes to Redis and what to the database."""

import json
from decimal import Decimal

from structlog.testing import capture_logs

from app.data.adapters.base import RawCandle
from app.stream.writer import CandleWriter

MINUTE = 60_000
T0 = 1_795_500_000_000  # ms, the start of a minute


def _row(minute: int, close: float = 100.0) -> list[float]:
    return [float(T0 + minute * MINUTE), 100.0, 101.0, 99.0, close, 5.0]


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, tuple[str, int | None]] = {}
        self.published: list[tuple[str, str]] = []

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.values[key] = (value, ex)

    async def publish(self, channel: str, message: str) -> None:
        self.published.append((channel, message))


class Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[RawCandle]]] = []

    async def __call__(self, symbol: str, candles: list[RawCandle]) -> int:
        self.calls.append((symbol, candles))
        return len(candles)

    @property
    def stored_minutes(self) -> list[int]:
        return [int((c.ts.timestamp() * 1000 - T0) // MINUTE) for _, cs in self.calls for c in cs]


class Clock:
    def __init__(self) -> None:
        self.now = float(T0)

    def __call__(self) -> float:
        return self.now


def _writer() -> tuple[CandleWriter, FakeRedis, Recorder, Clock]:
    redis, recorder, clock = FakeRedis(), Recorder(), Clock()
    return CandleWriter(redis, recorder, clock_ms=clock), redis, recorder, clock  # type: ignore[arg-type]


async def _feed(
    writer: CandleWriter, clock: Clock, minute: int, offset_s: float, **kw: float
) -> None:
    clock.now = T0 + minute * MINUTE + offset_s * 1000
    await writer.handle("BTC/USDT", [_row(minute, **kw)])


async def test_the_forming_candle_goes_to_redis_and_pubsub_not_the_database() -> None:
    writer, redis, recorder, clock = _writer()

    await _feed(writer, clock, 0, 10, close=123.45)

    value, ttl = redis.values["live:binance:BTC/USDT:1m"]
    assert json.loads(value)["close"] == "123.45"  # exact decimal string
    assert ttl == 300
    assert redis.published == [("candles:binance:BTC/USDT:1m", value)]
    assert recorder.calls == []


async def test_a_candle_is_stored_when_the_next_one_starts_with_its_final_values() -> None:
    writer, _, recorder, clock = _writer()

    await _feed(writer, clock, 0, 1)
    await _feed(writer, clock, 0, 30, close=102)
    await _feed(writer, clock, 0, 60.1, close=103)  # the final update, just after the close
    assert recorder.calls == []  # not yet: it could still change until a newer candle shows up
    await _feed(writer, clock, 1, 1)

    assert recorder.stored_minutes == [0]
    assert recorder.calls[0][1][0].close == Decimal("103.0")


async def test_a_candle_cut_short_by_a_disconnect_is_not_stored() -> None:
    writer, _, recorder, clock = _writer()

    await _feed(writer, clock, 0, 20)  # last update for minute 0 arrives at 20s
    with capture_logs() as logs:
        await _feed(writer, clock, 1, 5)  # reconnected in the next minute

    assert recorder.calls == []
    assert any(log["event"] == "stream_candle_incomplete" for log in logs)


async def test_each_closed_candle_is_stored_once_and_replays_are_ignored() -> None:
    writer, _, recorder, clock = _writer()
    for minute in range(3):
        await _feed(writer, clock, minute, 60.2 if minute else 61)
    clock.now = T0 + 3 * MINUTE
    await writer.handle("BTC/USDT", [_row(0), _row(1)])  # an old replay

    assert recorder.stored_minutes == [0, 1]  # minute 2 is still the forming one


async def test_symbols_are_tracked_separately() -> None:
    writer, _, recorder, clock = _writer()
    for symbol in ("BTC/USDT", "ETH/USDT"):
        clock.now = T0 + 61 * 1000
        await writer.handle(symbol, [_row(0)])
        clock.now = T0 + MINUTE + 1000
        await writer.handle(symbol, [_row(1)])

    assert [symbol for symbol, _ in recorder.calls] == ["BTC/USDT", "ETH/USDT"]


async def test_empty_updates_are_ignored_and_batches_are_applied_in_order() -> None:
    writer, redis, recorder, clock = _writer()
    await writer.handle("BTC/USDT", [])
    assert redis.values == {}

    clock.now = T0 + 2 * MINUTE + 1000
    await writer.handle("BTC/USDT", [_row(1), _row(0)])  # out of order within one update
    assert recorder.stored_minutes == [0]  # applied oldest first: 0 becomes current, 1 closes it
