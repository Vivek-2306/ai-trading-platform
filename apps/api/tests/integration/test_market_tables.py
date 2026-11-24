"""The candle tables against a real TimescaleDB."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import insert, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.data.models import Candle, Instrument

pytestmark = pytest.mark.integration

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"
T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _migrate(url: str) -> None:
    config = Config(str(ALEMBIC_INI))
    config.attributes["configure_logger"] = False
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")


def _candle(instrument_id: int, **overrides: object) -> Candle:
    values: dict[str, object] = {
        "instrument_id": instrument_id,
        "timeframe": "1h",
        "ts": T0,
        "open": Decimal("100.1234567891"),
        "high": Decimal("110"),
        "low": Decimal("90"),
        "close": Decimal("105"),
        "volume": Decimal("12.5"),
    }
    values.update(overrides)
    return Candle(**values)


def _run[T](url: str, work: Callable[[AsyncSession], Awaitable[T]]) -> T:
    async def go() -> T:
        engine = create_async_engine(url)
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                return await work(session)
        finally:
            await engine.dispose()

    return asyncio.run(go())


def test_migration_makes_candles_a_hypertable(postgres_url: str) -> None:
    _migrate(postgres_url)

    async def work(session: AsyncSession) -> set[str]:
        row = await session.execute(
            text("SELECT hypertable_name FROM timescaledb_information.hypertables")
        )
        return {r[0] for r in row}

    assert _run(postgres_url, work) == {"candles"}


def test_price_round_trips_as_decimal_and_duplicates_are_rejected(postgres_url: str) -> None:
    _migrate(postgres_url)

    async def work(session: AsyncSession) -> Decimal:
        instrument = Instrument(venue="binance", symbol="BTC/USDT", asset_class="crypto")
        session.add(instrument)
        await session.flush()
        session.add(_candle(instrument.id))
        await session.commit()

        stored_open = (await session.execute(select(Candle.open))).scalar_one()
        instrument_id = instrument.id
        with pytest.raises(IntegrityError):
            await session.execute(
                insert(Candle).values(
                    instrument_id=instrument_id,
                    timeframe="1h",
                    ts=T0,
                    open=1,
                    high=2,
                    low=1,
                    close=1,
                    volume=0,
                )
            )
        await session.rollback()
        return stored_open

    value = _run(postgres_url, work)
    assert isinstance(value, Decimal)
    assert value == Decimal("100.1234567891")


def test_bad_candles_are_rejected(postgres_url: str) -> None:
    _migrate(postgres_url)

    async def work(session: AsyncSession) -> None:
        instrument = Instrument(venue="binance", symbol="ETH/USDT", asset_class="crypto")
        session.add(instrument)
        await session.flush()
        for bad in (
            {"high": Decimal("1"), "low": Decimal("2")},
            {"volume": Decimal("-1")},
            {"timeframe": "7m"},
        ):
            session.add(_candle(instrument.id, **bad))
            with pytest.raises(IntegrityError):
                await session.commit()
            await session.rollback()

    _run(postgres_url, work)


def test_insert_candles_is_idempotent(postgres_url: str) -> None:
    from app.data.adapters.base import RawCandle
    from app.data.models import AssetClass, Timeframe
    from app.data.repository import get_or_create_instrument, insert_candles, latest_candle_time
    from app.data.universe import InstrumentSpec

    _migrate(postgres_url)
    candles = [
        RawCandle(
            T0 + timedelta(hours=i),
            Decimal(1),
            Decimal(2),
            Decimal(1),
            Decimal(2),
            Decimal(3),
        )
        for i in range(5)
    ]

    async def work(session: AsyncSession) -> tuple[int, int, int, datetime | None, bool]:
        # Own symbol: the database is shared by every test in the session.
        spec = InstrumentSpec("binance", "SOL/USDT", AssetClass.CRYPTO)
        first = await get_or_create_instrument(session, spec)
        again = await get_or_create_instrument(session, spec)
        new_first = await insert_candles(session, first.id, Timeframe.H1, candles)
        new_second = await insert_candles(session, first.id, Timeframe.H1, candles[:3])
        latest = await latest_candle_time(session, first.id, Timeframe.H1)
        return new_first, new_second, len(candles), latest, first.id == again.id

    new_first, new_second, total, latest, same_instrument = _run(postgres_url, work)
    assert (new_first, new_second) == (5, 0)
    assert latest == candles[-1].ts
    assert same_instrument
    assert total == 5


def test_backfill_task_stores_candles_and_a_rerun_adds_none(
    postgres_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import Settings
    from app.data.adapters.base import RawCandle
    from app.worker import tasks

    _migrate(postgres_url)
    recent = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(days=2)
    source = [
        RawCandle(
            recent + timedelta(hours=i),
            Decimal(1),
            Decimal(2),
            Decimal(1),
            Decimal(2),
            Decimal(3),
        )
        for i in range(30)
    ]

    class Fake:
        venue = "binance"

        async def fetch_candles(
            self, symbol: str, timeframe: object, since: datetime | None = None, limit: int = 500
        ) -> list[RawCandle]:
            return [c for c in source if since is None or c.ts >= since][:limit]

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(
        tasks, "get_settings", lambda: Settings(_env_file=None, database_url=postgres_url)
    )
    monkeypatch.setattr(tasks, "build_adapter", lambda venue, settings: Fake())

    first = tasks.backfill_candles.apply(args=("binance", "BTC/USDT", "crypto", "1h", 1)).get()
    second = tasks.backfill_candles.apply(args=("binance", "BTC/USDT", "crypto", "1h", 1)).get()

    assert (first, second) == (30, 0)


def test_update_instrument_fetches_new_candles_and_refills_a_gap(postgres_url: str) -> None:
    from app.data.adapters.base import RawCandle
    from app.data.models import AssetClass, Timeframe
    from app.data.repository import get_or_create_instrument, insert_candles
    from app.data.universe import InstrumentSpec
    from app.data.update import update_instrument

    _migrate(postgres_url)
    now = datetime(2026, 3, 1, 12, 30, tzinfo=UTC)
    start = datetime(2026, 3, 1, 0, tzinfo=UTC)  # 12 closed hourly candles by 12:00
    full = [
        RawCandle(
            start + timedelta(hours=i), Decimal(1), Decimal(2), Decimal(1), Decimal(2), Decimal(3)
        )
        for i in range(12)
    ]
    spec = InstrumentSpec("binance", "ADA/USDT", AssetClass.CRYPTO)

    class Source:
        venue = "binance"

        async def fetch_candles(
            self, symbol: str, timeframe: object, since: datetime | None = None, limit: int = 500
        ) -> list[RawCandle]:
            return [c for c in full if since is None or c.ts >= since][:limit]

        async def aclose(self) -> None:
            return None

    async def work(session: AsyncSession) -> tuple[int, int, int, int]:
        bind = session.bind
        sessions = async_sessionmaker(bind, expire_on_commit=False)
        instrument = await get_or_create_instrument(session, spec)
        await session.commit()
        # Stored: hours 0-3 and 8-9, so there is a hole at 4-7 and new data after 9.
        stored = [c for c in full if c.ts.hour in (0, 1, 2, 3, 8, 9)]
        await insert_candles(session, instrument.id, Timeframe.H1, stored)
        first = await update_instrument(sessions, Source(), spec, Timeframe.H1, now=now)
        second = await update_instrument(sessions, Source(), spec, Timeframe.H1, now=now)
        return first.new, first.gaps_found, first.gaps_refilled, second.new

    new, gaps_found, refilled, second_new = _run(postgres_url, work)
    assert new == 6  # hours 4-7 (gap) and 10-11 (new)
    assert gaps_found == 1
    assert refilled == 1
    assert second_new == 0


def test_update_task_survives_one_failing_instrument(
    postgres_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import Settings
    from app.data.adapters.base import AdapterError
    from app.worker import tasks

    _migrate(postgres_url)

    class Flaky:
        venue = "binance"

        async def fetch_candles(
            self, symbol: str, timeframe: object, since: datetime | None = None, limit: int = 500
        ) -> list[object]:
            if symbol == "ETH/USDT":
                raise AdapterError("boom")
            return []

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(
        tasks, "get_settings", lambda: Settings(_env_file=None, database_url=postgres_url)
    )
    monkeypatch.setattr(tasks, "build_adapter", lambda venue, settings: Flaky())

    result = tasks.update_candles.apply().get()

    assert result["binance:BTC/USDT:1h"] == 0
    assert "binance:ETH/USDT:1h" not in result
    assert "binance:PAXG/USDT:1d" in result


def test_quality_endpoint_reports_per_instrument(postgres_url: str, redis_url: str) -> None:
    from fastapi.testclient import TestClient

    from app.core.config import Settings
    from app.main import create_app

    _migrate(postgres_url)
    settings = Settings(
        _env_file=None, app_env="test", database_url=postgres_url, redis_url=redis_url
    )

    with TestClient(create_app(settings)) as client:
        response = client.get("/data/quality")

    body = response.json()
    assert response.status_code == 200
    keys = {(i["symbol"], i["timeframe"]) for i in body["instruments"]}
    assert ("BTC/USDT", "1h") in keys
    assert ("PAXG/USDT", "1d") in keys
    assert ("XAU/USD", "1h") not in keys  # no Twelve Data key set
    assert body["ok"] is False  # nothing loaded in this fresh database


def test_instruments_and_candles_endpoints(postgres_url: str, redis_url: str) -> None:
    from fastapi.testclient import TestClient

    from app.core.config import Settings
    from app.data.adapters.base import RawCandle
    from app.data.models import AssetClass, Timeframe
    from app.data.repository import get_or_create_instrument, insert_candles
    from app.data.universe import InstrumentSpec
    from app.main import create_app

    _migrate(postgres_url)
    base = datetime(2026, 2, 1, tzinfo=UTC)
    candles = [
        RawCandle(
            base + timedelta(hours=i),
            Decimal("100.1234567891"),
            Decimal(2) + i,
            Decimal(1),
            Decimal(2),
            Decimal(3),
        )
        for i in range(10)
    ]

    async def seed(session: AsyncSession) -> int:
        spec = InstrumentSpec("binance", "DOGE/USDT", AssetClass.CRYPTO)
        instrument = await get_or_create_instrument(session, spec)
        await insert_candles(session, instrument.id, Timeframe.H1, candles)
        return instrument.id

    instrument_id = _run(postgres_url, seed)
    settings = Settings(
        _env_file=None, app_env="test", database_url=postgres_url, redis_url=redis_url
    )
    with TestClient(create_app(settings)) as client:
        listing = client.get("/data/instruments").json()
        page1 = client.get(
            "/data/candles", params={"instrument_id": instrument_id, "timeframe": "1h", "limit": 4}
        ).json()
        page2 = client.get(
            "/data/candles",
            params={
                "instrument_id": instrument_id,
                "timeframe": "1h",
                "limit": 4,
                "before": page1["next_before"],
            },
        ).json()
        last = client.get(
            "/data/candles",
            params={
                "instrument_id": instrument_id,
                "timeframe": "1h",
                "limit": 4,
                "before": page2["next_before"],
            },
        ).json()
        missing = client.get("/data/candles", params={"instrument_id": 99999, "timeframe": "1h"})
        naive = client.get(  # no timezone: treated as UTC
            "/data/candles",
            params={
                "instrument_id": instrument_id,
                "timeframe": "1h",
                "before": "2026-02-01T03:00:00",
            },
        ).json()

    assert any(i["symbol"] == "DOGE/USDT" and i["id"] == instrument_id for i in listing)
    # Newest four first page, oldest-first inside the page.
    assert [c["ts"][:13] for c in page1["candles"]] == [
        "2026-02-01T06",
        "2026-02-01T07",
        "2026-02-01T08",
        "2026-02-01T09",
    ]
    assert page1["candles"][0]["open"] == "100.1234567891"  # exact decimal string
    assert len(page2["candles"]) == 4 and page2["candles"][-1]["ts"][:13] == "2026-02-01T05"
    assert len(last["candles"]) == 2 and last["next_before"] is None
    assert missing.status_code == 404
    assert [c["ts"][:13] for c in naive["candles"]] == [
        "2026-02-01T00",
        "2026-02-01T01",
        "2026-02-01T02",
    ]
