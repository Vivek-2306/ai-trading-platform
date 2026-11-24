"""Twelve Data adapter checks against a response shaped like the documented API. No network.

The fixture is written from Twelve Data's documented time_series format, not recorded live
(a free API key is needed for that).
"""

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from app.data.adapters.base import AdapterError
from app.data.adapters.twelvedata import TwelveDataAdapter
from app.data.models import Timeframe
from tests.adapter_contract import assert_adapter_contract

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "twelvedata_xauusd_1h.json").read_text())
KEY = SecretStr("test-key-123")


def _adapter(handler: httpx.MockTransport | None, attempts: int = 3) -> TwelveDataAdapter:
    client = httpx.AsyncClient(base_url="https://api.twelvedata.com", transport=handler)
    return TwelveDataAdapter(KEY, client, attempts=attempts, max_wait_seconds=0.01)


def _ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=FIXTURE)


async def test_meets_the_adapter_contract() -> None:
    adapter = _adapter(httpx.MockTransport(_ok))

    await assert_adapter_contract(adapter, "XAU/USD", Timeframe.H1, datetime.now(UTC))


async def test_parses_prices_as_decimals_with_zero_volume() -> None:
    candles = await _adapter(httpx.MockTransport(_ok)).fetch_candles("XAU/USD", Timeframe.H1)

    assert candles[0].ts == datetime(2026, 1, 5, 10, tzinfo=UTC)
    assert candles[0].open == Decimal("2650.10")
    assert candles[0].volume == Decimal(0)


async def test_sends_the_expected_query() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=FIXTURE)

    since = datetime(2026, 1, 5, 10, tzinfo=UTC)
    await _adapter(httpx.MockTransport(handler)).fetch_candles(
        "XAU/USD", Timeframe.H1, since=since, limit=10
    )

    params = seen[0].url.params
    assert params["symbol"] == "XAU/USD"
    assert params["interval"] == "1h"
    assert params["outputsize"] == "10"
    assert params["start_date"] == "2026-01-05 10:00:00"
    assert params["timezone"] == "UTC"


async def test_retries_a_rate_limit_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(200, json={"code": 429, "message": "limit", "status": "error"})
        return httpx.Response(200, json=FIXTURE)

    candles = await _adapter(httpx.MockTransport(handler)).fetch_candles("XAU/USD", Timeframe.H1)

    assert calls["n"] == 2
    assert candles


async def test_gives_up_when_always_rate_limited() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429)

    with pytest.raises(AdapterError, match="rate limited"):
        await _adapter(httpx.MockTransport(handler), attempts=2).fetch_candles(
            "XAU/USD", Timeframe.H1
        )


async def test_api_errors_and_odd_responses_raise_adapter_error() -> None:
    def bad_symbol(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 400, "message": "bad", "status": "error"})

    def odd(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "ok"})

    with pytest.raises(AdapterError, match="400"):
        await _adapter(httpx.MockTransport(bad_symbol)).fetch_candles("NOPE", Timeframe.H1)
    with pytest.raises(AdapterError, match="unexpected"):
        await _adapter(httpx.MockTransport(odd)).fetch_candles("XAU/USD", Timeframe.H1)


async def test_the_api_key_never_appears_in_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    with pytest.raises(AdapterError) as info:
        await _adapter(httpx.MockTransport(handler)).fetch_candles("XAU/USD", Timeframe.H1)

    assert "test-key-123" not in str(info.value)
    assert "test-key-123" not in repr(info.value.__cause__)


async def test_a_network_failure_does_not_leak_the_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"cannot reach {request.url}", request=request)

    with pytest.raises(AdapterError) as info:
        await _adapter(httpx.MockTransport(handler), attempts=2).fetch_candles(
            "XAU/USD", Timeframe.H1
        )

    assert "ConnectError" in str(info.value)
    assert "test-key-123" not in str(info.value)
    assert "test-key-123" not in repr(info.value.__cause__)
    retryable = info.value.__cause__
    assert retryable is not None
    assert retryable.__cause__ is None
    assert "test-key-123" not in repr(retryable.__context__)


async def test_aclose_closes_the_client() -> None:
    adapter = _adapter(httpx.MockTransport(_ok))

    await adapter.aclose()

    assert adapter._client.is_closed
