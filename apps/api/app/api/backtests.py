"""Stored backtest results (read-only). Running one is a command-line or background job."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import load_only

from app.core.database import SessionDep
from app.data.models import BacktestRun, Instrument, Timeframe

router = APIRouter(prefix="/backtests", tags=["backtests"])

MAX_TRADES = 200


class BacktestSummary(BaseModel):
    id: int
    created_at: datetime
    symbol: str
    timeframe: str
    strategy: str
    segment: str
    config_hash: str
    range_start: datetime
    range_end: datetime
    candle_count: int
    code_version: str
    metrics: dict[str, Any]
    # What the strategy did compared with buy-and-hold, with a plain-language verdict.
    benchmark: dict[str, Any]


class BacktestDetail(BacktestSummary):
    config: dict[str, Any]
    data_fingerprint: str
    # The latest trades only (at most MAX_TRADES); `trade_count` is how many there were.
    trades: list[dict[str, Any]]
    trade_count: int
    # Downsampled equity curves: {"times": [...], "strategy": [...], "benchmark": [...]}.
    equity: dict[str, Any]
    details: dict[str, Any]


def _summary_fields(run: BacktestRun, symbol: str) -> dict[str, Any]:
    return {
        "id": run.id,
        "created_at": run.created_at,
        "symbol": symbol,
        "timeframe": run.timeframe,
        "strategy": run.strategy,
        "segment": run.segment,
        "config_hash": run.config_hash,
        "range_start": run.range_start,
        "range_end": run.range_end,
        "candle_count": run.candle_count,
        "code_version": run.code_version,
        "metrics": run.metrics,
        "benchmark": run.benchmark,
    }


@router.get("", summary="List backtest runs")
async def list_backtests(
    session: SessionDep,
    symbol: str | None = None,
    timeframe: Timeframe | None = None,
    segment: Annotated[str | None, Query(pattern="^(tuning|walk_forward|oos)$")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> list[BacktestSummary]:
    """Newest first. Past results with simulated costs: not a forecast and not advice."""
    summary_columns = [
        getattr(BacktestRun, name)
        for name in (
            "id",
            "created_at",
            "instrument_id",
            "timeframe",
            "strategy",
            "segment",
            "config_hash",
            "range_start",
            "range_end",
            "candle_count",
            "code_version",
            "metrics",
            "benchmark",
        )
    ]
    statement = (
        select(BacktestRun, Instrument.symbol)
        .options(load_only(*summary_columns))  # not the big trades / curves JSON
        .join(Instrument, Instrument.id == BacktestRun.instrument_id)
        .order_by(BacktestRun.id.desc())
        .limit(limit)
    )
    if symbol:
        statement = statement.where(Instrument.symbol == symbol)
    if timeframe:
        statement = statement.where(BacktestRun.timeframe == timeframe.value)
    if segment:
        statement = statement.where(BacktestRun.segment == segment)
    rows = (await session.execute(statement)).all()
    return [BacktestSummary(**_summary_fields(run, sym)) for run, sym in rows]


@router.get(
    "/{run_id}",
    summary="One backtest run in full",
    responses={404: {"description": "Unknown run"}},
)
async def get_backtest(
    session: SessionDep, run_id: Annotated[int, Path(ge=1, le=2**63 - 1)]
) -> BacktestDetail:
    row = (
        await session.execute(
            select(BacktestRun, Instrument.symbol)
            .join(Instrument, Instrument.id == BacktestRun.instrument_id)
            .where(BacktestRun.id == run_id)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    run, symbol = row
    return BacktestDetail(
        **_summary_fields(run, symbol),
        config=run.config,
        data_fingerprint=run.data_fingerprint,
        trades=run.trades[-MAX_TRADES:],
        trade_count=len(run.trades),
        equity=run.equity,
        details=run.details,
    )
