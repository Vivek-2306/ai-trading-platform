"""Signal endpoints (read-only: signals are appended by the signal job, never edited)."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from app.core.database import SessionDep
from app.data.models import Instrument, Signal, SignalAction, Timeframe
from app.risk.killswitch import kill_switch_state
from app.signals.runner import STALE_AFTER_CANDLES

router = APIRouter(prefix="/signals", tags=["signals"])


class ReasonOut(BaseModel):
    code: str
    text: str
    direction: str  # buy, sell, neutral or info
    weight: float = 0.0


class VetoOut(BaseModel):
    code: str
    text: str


class PlanOut(BaseModel):
    """Prices as exact decimal strings."""

    entry: Decimal
    stop: Decimal
    target: Decimal
    risk_per_unit: Decimal
    reward_per_unit: Decimal
    risk_reward: Decimal


class SizeOut(BaseModel):
    quantity: Decimal
    notional: Decimal
    risk_amount: Decimal
    capital_share_pct: Decimal
    limited_by: str


class RiskOut(BaseModel):
    """The risk engine's verdict on a signal."""

    # False for signals from before the risk engine existed: treat them as not actionable.
    assessed: bool = False
    # False until paper trading exists: the open-position and daily-loss limits are not enforced
    # yet because there is no position data to check against.
    portfolio_tracked: bool = False
    # What the rule engine said before the risk veto (a refused BUY reads BUY here and
    # NO_TRADE in `action`).
    rules_action: SignalAction | None = None
    kill_switch: bool = False
    vetoes: list[VetoOut] = []
    plan: PlanOut | None = None  # only for an actionable BUY
    size: SizeOut | None = None


class SignalOut(BaseModel):
    id: int
    instrument_id: int
    symbol: str
    venue: str
    timeframe: str
    candle_ts: datetime
    action: SignalAction
    # How much of the rule weight agrees with the leading side, 0 to 1. Not a probability.
    confidence: Decimal
    reasons: list[ReasonOut]
    inputs: dict[str, Any]
    rule_version: str
    created_at: datetime
    risk: RiskOut = RiskOut()
    # BUY or SELL that passed the risk veto and is not stale. Everything else: do nothing.
    actionable: bool = False
    # True when the candle this signal is about is old (feed or job stopped): do not act on it.
    stale: bool = False


class SignalsResponse(BaseModel):
    signals: list[SignalOut]
    # Pass as `before_id` to get the next older page; null when there is nothing older.
    next_before_id: int | None


def _out(
    signal: Signal,
    instrument: Instrument,
    now: datetime | None = None,
    kill_switch_on: bool = False,
) -> SignalOut:
    now = now or datetime.now(UTC)
    seconds = Timeframe(signal.timeframe).seconds
    record = signal.risk or {}
    action = SignalAction(signal.action)
    is_stale = (now - signal.candle_ts).total_seconds() > seconds * STALE_AFTER_CANDLES
    assessed = record.get("assessed") is True
    show_plan = assessed and action is SignalAction.BUY
    # The kill switch is read when serving, not only when the signal was made: a BUY stored
    # before the switch was turned on must not stay actionable.
    show_plan = show_plan and not kill_switch_on
    vetoes = [VetoOut(**v) for v in record.get("vetoes", [])]
    if kill_switch_on and not any(v.code == "kill_switch" for v in vetoes):
        vetoes.append(
            VetoOut(code="kill_switch", text="The kill switch is on: nothing is actionable.")
        )
    risk = RiskOut(
        assessed=assessed,
        portfolio_tracked=bool(record.get("portfolio_tracked", False)),
        rules_action=record.get("rules_action"),
        kill_switch=kill_switch_on or bool(record.get("kill_switch", False)),
        vetoes=vetoes,
        plan=PlanOut(**record["plan"]) if show_plan and "plan" in record else None,
        size=SizeOut(**record["size"]) if show_plan and "size" in record else None,
    )
    return SignalOut(
        id=signal.id,
        instrument_id=signal.instrument_id,
        symbol=instrument.symbol,
        venue=instrument.venue,
        timeframe=signal.timeframe,
        candle_ts=signal.candle_ts,
        action=SignalAction(signal.action),
        confidence=signal.confidence,
        reasons=[ReasonOut(**reason) for reason in signal.reasons],
        inputs=signal.inputs,
        rule_version=signal.rule_version,
        created_at=signal.created_at,
        risk=risk,
        actionable=assessed
        and not is_stale
        and not kill_switch_on
        and action in (SignalAction.BUY, SignalAction.SELL),
        stale=is_stale,
    )


@router.get("", summary="List signals")
async def list_signals(
    session: SessionDep,
    instrument_id: Annotated[int | None, Query(ge=1)] = None,
    timeframe: Timeframe | None = None,
    action: SignalAction | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    before_id: Annotated[int | None, Query(ge=1)] = None,
) -> SignalsResponse:
    """Signals, newest recorded first. Filter by instrument, timeframe or action; page back with
    `next_before_id`. Research output, not financial advice."""
    statement = (
        select(Signal, Instrument)
        .join(Instrument, Instrument.id == Signal.instrument_id)
        .order_by(Signal.id.desc())
        .limit(limit)
    )
    if instrument_id is not None:
        statement = statement.where(Signal.instrument_id == instrument_id)
    if timeframe is not None:
        statement = statement.where(Signal.timeframe == timeframe.value)
    if action is not None:
        statement = statement.where(Signal.action == action.value)
    if before_id is not None:
        statement = statement.where(Signal.id < before_id)
    rows = (await session.execute(statement)).all()
    switch_on = (await kill_switch_state(session)).active
    items = [_out(signal, instrument, kill_switch_on=switch_on) for signal, instrument in rows]
    return SignalsResponse(
        signals=items, next_before_id=items[-1].id if len(items) == limit else None
    )


@router.get("/latest", summary="Latest signal per instrument and timeframe")
async def latest_signals(session: SessionDep) -> list[SignalOut]:
    """The newest signal for every instrument and timeframe that has one."""
    rank = (
        func.row_number()
        .over(
            partition_by=(Signal.instrument_id, Signal.timeframe),
            order_by=(Signal.candle_ts.desc(), Signal.id.desc()),
        )
        .label("rank")
    )
    newest = select(Signal.id, rank).subquery()
    rows = (
        await session.execute(
            select(Signal, Instrument)
            .join(Instrument, Instrument.id == Signal.instrument_id)
            .where(Signal.id.in_(select(newest.c.id).where(newest.c.rank == 1)))
            .order_by(Instrument.venue, Instrument.symbol, Signal.timeframe)
        )
    ).all()
    switch_on = (await kill_switch_state(session)).active
    return [_out(signal, instrument, kill_switch_on=switch_on) for signal, instrument in rows]
