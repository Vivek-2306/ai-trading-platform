"""Market data endpoints."""

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import SettingsDep
from app.core.database import SessionDep
from app.data.models import Timeframe
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
