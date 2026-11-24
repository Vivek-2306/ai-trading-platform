"""Produce and store a signal for an instrument and timeframe.

Run after candles close. It reads the stored (closed) candles, computes features, asks the
rule engine, and appends the result. One signal exists per instrument, timeframe, candle and
rule version, so running it twice for the same candle stores it once.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.analysis.features import compute_features, latest
from app.analysis.indicators import CandleSeries
from app.core.logging import get_logger
from app.data.adapters.base import RawCandle
from app.data.gaps import find_gaps
from app.data.models import Candle, Instrument, Signal, SignalAction, Timeframe
from app.data.repository import record_signal
from app.data.universe import InstrumentSpec
from app.risk.killswitch import kill_switch_state
from app.risk.limits import get_risk_limits
from app.risk.veto import RiskAssessment, assess, current_portfolio_state
from app.signals.rules import Decision, RuleConfig, evaluate, no_trade

logger = get_logger(__name__)

HISTORY_CANDLES = 300
# If the newest stored candle is older than this many candle lengths, the data is lagging and
# a signal about it would be misleading.
STALE_AFTER_CANDLES = 3


@dataclass(frozen=True, slots=True)
class RunResult:
    symbol: str
    timeframe: str
    candle_ts: datetime
    action: SignalAction
    stored: bool  # False when this candle already had a signal


async def load_series(
    session: AsyncSession, instrument_id: int, timeframe: Timeframe, limit: int = HISTORY_CANDLES
) -> CandleSeries:
    rows = (
        await session.execute(
            select(Candle)
            .where(Candle.instrument_id == instrument_id, Candle.timeframe == timeframe.value)
            .order_by(Candle.ts.desc())
            .limit(limit)
        )
    ).scalars()
    candles = [
        RawCandle(c.ts, c.open, c.high, c.low, c.close, c.volume) for c in reversed(list(rows))
    ]
    return CandleSeries.from_candles(candles)


def to_signal(
    instrument_id: int,
    timeframe: Timeframe,
    candle_ts: datetime,
    d: Decision,
    assessment: RiskAssessment,
) -> Signal:
    """The only place a Signal is built. It needs the risk assessment, so a rule decision can
    never be stored without having been through the veto layer."""
    reasons = [r.as_dict() for r in d.reasons]
    reasons += [
        {"code": f"risk_{v.code}", "text": v.text, "direction": "info", "weight": 0.0}
        for v in assessment.vetoes
    ]
    if assessment.action is SignalAction.BUY and assessment.plan and assessment.size:
        reasons.append(
            {
                "code": "risk_plan",
                "text": (
                    f"Plan: buy near {assessment.plan.entry}, stop {assessment.plan.stop}, "
                    f"target {assessment.plan.target}, size {assessment.size.quantity} "
                    f"(risking {assessment.size.risk_amount}, risk-to-reward "
                    f"{assessment.plan.risk_reward})."
                ),
                "direction": "info",
                "weight": 0.0,
            }
        )
    return Signal(
        instrument_id=instrument_id,
        timeframe=timeframe.value,
        candle_ts=candle_ts,
        action=assessment.action.value,  # after the veto, not what the rules first said
        confidence=d.confidence,
        reasons=reasons,
        inputs={k: v for k, v in d.inputs.items()},
        rule_version=d.rule_version,
        risk=assessment.as_record(),
    )


async def run_signal(
    sessions: async_sessionmaker[AsyncSession],
    spec: InstrumentSpec,
    timeframe: Timeframe,
    *,
    now: datetime | None = None,
    config: RuleConfig | None = None,
) -> RunResult | None:
    """Decide for the newest closed candle and store it. None if there is nothing to decide on
    (no candles, or the data is stale)."""
    now = now or datetime.now(UTC)
    async with sessions() as session:
        instrument = (
            await session.execute(
                select(Instrument).where(
                    Instrument.venue == spec.venue, Instrument.symbol == spec.symbol
                )
            )
        ).scalar_one_or_none()
        if instrument is None:
            return None
        series = await load_series(session, instrument.id, timeframe)
        if len(series) == 0:
            return None
        newest = series.times[-1]
        if now - newest > timedelta(seconds=timeframe.seconds * STALE_AFTER_CANDLES):
            logger.warning(
                "signal_skipped_stale_data",
                symbol=spec.symbol,
                timeframe=timeframe.value,
                newest=newest.isoformat(),
            )
            return None
        step = timedelta(seconds=timeframe.seconds)
        expected = (
            datetime.fromtimestamp(
                (int(now.timestamp()) // timeframe.seconds) * timeframe.seconds, tz=UTC
            )
            - step
        )
        if newest < expected:
            # The candle that just closed is not stored yet (the update job is late). Skip: a
            # signal about the previous candle would be old news; the next run catches up.
            logger.warning(
                "signal_skipped_late_candle",
                symbol=spec.symbol,
                timeframe=timeframe.value,
                newest=newest.isoformat(),
                expected=expected.isoformat(),
            )
            return None
        features = compute_features(series)
        gaps = find_gaps(series.times, spec.venue, timeframe, series.times[0], newest + step)
        if gaps:
            # Indicators assume consecutive candles; missing ones would distort them.
            decision = no_trade(
                "data_gap",
                f"{sum(g.count for g in gaps)} candle(s) are missing from the recent history.",
                "Gap in the data",
                latest(features),
            )
        else:
            decision = evaluate(features, config)
        # Every decision, including data gaps, goes through the risk veto before it is stored.
        assessment = assess(
            decision,
            symbol=spec.symbol,
            entry=series.last_close,
            atr=decision.inputs.get("atr"),
            limits=get_risk_limits(),
            state=current_portfolio_state(),
            kill_switch_on=(await kill_switch_state(session)).active,
        )
        stored = await record_signal(
            session, to_signal(instrument.id, timeframe, newest, decision, assessment)
        )
    logger.info(
        "signal",
        symbol=spec.symbol,
        timeframe=timeframe.value,
        candle=newest.isoformat(),
        rules_action=decision.action.value,
        action=assessment.action.value,
        vetoes=[v.code for v in assessment.vetoes],
        confidence=str(Decimal(decision.confidence)),
        stored=stored,
    )
    return RunResult(spec.symbol, timeframe.value, newest, assessment.action, stored)
