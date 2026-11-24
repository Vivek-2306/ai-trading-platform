"""Market data endpoints."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import SettingsDep
from app.core.database import SessionDep
from app.data.models import Candle, Instrument, Timeframe
from app.data.quality import check_instrument
from app.data.universe import default_universe

router = APIRouter(prefix="/data", tags=["data"])

CHECKED_TIMEFRAMES = (Timeframe.H1, Timeframe.D1)


class InstrumentQuality(BaseModel):
    venue: str
    symbol: str
    timeframe: str
    ok: bool
    candles: int
    latest: datetime | None
    missing_candles: int
    gap_runs: int
    stale: bool
    inconsistent_candles: int
    spikes: int


class QualityResponse(BaseModel):
    ok: bool
    instruments: list[InstrumentQuality]


@router.get("/quality", summary="Data-quality report")
async def quality(session: SessionDep, settings: SettingsDep) -> QualityResponse:
    """Per instrument and timeframe, over the last 30 days: missing candles (market-hours
    aware), stale data, candles whose open or close lies outside high-low, and price spikes."""
    specs = default_universe(twelve_data_enabled=settings.twelve_data_api_key is not None)
    items: list[InstrumentQuality] = []
    for spec in specs:
        for timeframe in CHECKED_TIMEFRAMES:
            report = await check_instrument(session, spec, timeframe)
            items.append(
                InstrumentQuality(
                    venue=report.venue,
                    symbol=report.symbol,
                    timeframe=report.timeframe,
                    ok=report.ok,
                    candles=report.candles,
                    latest=report.latest,
                    missing_candles=report.missing_candles,
                    gap_runs=report.gap_runs,
                    stale=report.stale,
                    inconsistent_candles=report.inconsistent_candles,
                    spikes=report.spikes,
                )
            )
    return QualityResponse(ok=all(item.ok for item in items), instruments=items)


class InstrumentOut(BaseModel):
    id: int
    venue: str
    symbol: str
    asset_class: str
    active: bool


class CandleOut(BaseModel):
    """Prices are decimal strings in JSON, so no precision is lost."""

    ts: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


class CandlesResponse(BaseModel):
    instrument_id: int
    timeframe: Timeframe
    candles: list[CandleOut]
    # Pass as `before` to get the next older page; null when there is nothing older.
    next_before: datetime | None


@router.get("/instruments", summary="List instruments")
async def instruments(session: SessionDep) -> list[InstrumentOut]:
    """Every instrument we hold candles for, ordered by venue and symbol."""
    rows = await session.execute(select(Instrument).order_by(Instrument.venue, Instrument.symbol))
    return [
        InstrumentOut(
            id=i.id, venue=i.venue, symbol=i.symbol, asset_class=i.asset_class, active=i.active
        )
        for i in rows.scalars()
    ]


@router.get(
    "/candles",
    summary="List candles",
    responses={404: {"description": "Unknown instrument"}},
)
async def candles(
    session: SessionDep,
    instrument_id: Annotated[int, Query(ge=1)],
    timeframe: Timeframe,
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
    before: Annotated[
        datetime | None, Query(description="Only candles opened before this time")
    ] = None,
) -> CandlesResponse:
    """The newest `limit` candles (oldest first). Page back in time with `next_before`."""
    if await session.get(Instrument, instrument_id) is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    statement = (
        select(Candle)
        .where(Candle.instrument_id == instrument_id, Candle.timeframe == timeframe.value)
        .order_by(Candle.ts.desc())
        .limit(limit)
    )
    if before is not None:
        statement = statement.where(Candle.ts < before)
    rows = list((await session.execute(statement)).scalars())
    rows.reverse()
    return CandlesResponse(
        instrument_id=instrument_id,
        timeframe=timeframe,
        candles=[
            CandleOut(ts=c.ts, open=c.open, high=c.high, low=c.low, close=c.close, volume=c.volume)
            for c in rows
        ],
        next_before=rows[0].ts if len(rows) == limit else None,
    )
