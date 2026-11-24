"""The SSE relay, with a fake Redis. Real-server behaviour is in the integration tests."""

import asyncio
import json
from typing import Any

import anyio
import pytest
from fastapi.testclient import TestClient

from app.api.stream import candle_events


class FakePubSub:
    def __init__(self, messages: list[Any]) -> None:
        self._messages = list(messages)
        self.subscribed: list[str] = []
        self.closed = False
        self.unsubscribed = False

    async def subscribe(self, channel: str) -> None:
        self.subscribed.append(channel)

    async def get_message(
        self,
        ignore_subscribe_messages: bool = False,
        timeout: float | None = None,  # noqa: ASYNC109 - mirrors redis-py's signature
    ) -> dict[str, Any] | None:
        if self._messages:
            return {"type": "message", "data": self._messages.pop(0)}
        await asyncio.sleep(timeout or 0)
        return None

    async def unsubscribe(self, channel: str) -> None:
        self.unsubscribed = True

    async def aclose(self) -> None:
        self.closed = True


class FakeRedis:
    def __init__(self, messages: list[Any], latest: str | None = None) -> None:
        self.pubsub_obj = FakePubSub(messages)
        self._latest = latest

    def pubsub(self) -> FakePubSub:
        return self.pubsub_obj

    async def get(self, key: str) -> str | None:
        assert key == "live:binance:BTC/USDT:1m"
        return self._latest


def _disconnect_after(checks: int) -> Any:
    state = {"n": 0}

    async def is_disconnected() -> bool:
        state["n"] += 1
        return state["n"] > checks

    return is_disconnected


async def _collect(redis: FakeRedis, checks: int, **kw: float) -> list[str]:
    chunks = []
    async for chunk in candle_events(
        redis,  # type: ignore[arg-type]
        "BTC/USDT",
        _disconnect_after(checks),
        poll_seconds=0.001,
        **kw,
    ):
        chunks.append(chunk)
    return chunks


async def test_sends_the_latest_candle_first_then_updates() -> None:
    redis = FakeRedis(['{"close": "2"}'], latest='{"close": "1"}')

    chunks = await _collect(redis, checks=1)

    assert chunks == [
        'event: candle\ndata: {"close": "1"}\n\n',
        'event: candle\ndata: {"close": "2"}\n\n',
    ]
    assert redis.pubsub_obj.subscribed == ["candles:binance:BTC/USDT:1m"]


async def test_a_backlog_is_conflated_to_the_newest_message() -> None:
    redis = FakeRedis([f'{{"close": "{i}"}}' for i in range(100)])

    chunks = await _collect(redis, checks=1)

    assert chunks == ['event: candle\ndata: {"close": "99"}\n\n']


async def test_keepalives_when_quiet() -> None:
    chunks = await _collect(FakeRedis([]), checks=20, keepalive_seconds=0.005)

    assert chunks and set(chunks) == {": keepalive\n\n"}


async def test_cleans_up_when_the_client_leaves() -> None:
    redis = FakeRedis([])

    await _collect(redis, checks=0)

    assert redis.pubsub_obj.unsubscribed and redis.pubsub_obj.closed


def test_unknown_symbol_is_404(client: TestClient) -> None:
    response = client.get("/data/stream", params={"symbol": "DOGE/USDT"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "http_404"


def test_symbol_is_required(client: TestClient) -> None:
    assert client.get("/data/stream").status_code == 422


def test_too_many_open_streams_is_503(client: TestClient) -> None:
    client.app.state.stream_clients = 50  # type: ignore[attr-defined]

    response = client.get("/data/stream", params={"symbol": "BTC/USDT"})

    assert response.status_code == 503


@pytest.mark.parametrize("payload", ['{"a": 1}', json.dumps({"ts": "x", "close": "1.5"})])
async def test_payload_is_passed_through_unchanged(payload: str) -> None:
    chunks = await _collect(FakeRedis([payload]), checks=1)

    assert chunks == [f"event: candle\ndata: {payload}\n\n"]


async def test_conflation_keeps_the_final_update_of_each_minute() -> None:
    messages = [
        '{"ts": "10:00", "close": "1"}',
        '{"ts": "10:00", "close": "2"}',  # the final value of minute 10:00
        '{"ts": "10:01", "close": "3"}',
        '{"ts": "10:01", "close": "4"}',
    ]

    chunks = await _collect(FakeRedis(messages), checks=1)

    assert chunks == [
        'event: candle\ndata: {"ts": "10:00", "close": "2"}\n\n',
        'event: candle\ndata: {"ts": "10:01", "close": "4"}\n\n',
    ]


class SlowCleanupPubSub(FakePubSub):
    """Cleanup that really suspends, as a network round trip does."""

    async def unsubscribe(self, channel: str) -> None:
        await asyncio.sleep(0.02)
        self.unsubscribed = True

    async def aclose(self) -> None:
        await asyncio.sleep(0.02)
        self.closed = True


async def test_cleanup_finishes_even_when_the_request_scope_is_cancelled() -> None:
    redis = FakeRedis([])
    redis.pubsub_obj = SlowCleanupPubSub([])

    async def consume() -> None:
        async for _ in candle_events(
            redis,  # type: ignore[arg-type]
            "BTC/USDT",
            _disconnect_after(10_000),
            poll_seconds=0.001,
        ):
            pass

    async with anyio.create_task_group() as group:  # what Starlette does when a client leaves
        group.start_soon(consume)
        await asyncio.sleep(0.05)
        group.cancel_scope.cancel()

    assert redis.pubsub_obj.unsubscribed and redis.pubsub_obj.closed
