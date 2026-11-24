"""The candle tables against a real TimescaleDB."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
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
