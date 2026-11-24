"""The risk veto: the only way a rule-engine decision becomes a stored, actionable signal.

`assess` takes what the rules decided and returns what the platform will actually say. A BUY
needs a valid trade plan and size and must respect the open-position and daily-loss limits;
with the kill switch on, nothing is actionable at all. Anything refused becomes NO_TRADE and
carries the reasons. The rule engine can ask; this decides.

Nothing outside the signal runner may build or store a signal (a test enforces that), so there
is no path from a rule decision to a stored signal that skips this module.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.data.models import SignalAction
from app.risk.limits import RiskLimits
from app.risk.plan import TradePlan, Veto, plan_long
from app.risk.sizing import PositionSize, position_size, quantity_step
from app.signals.rules import Decision

_ISSUER = object()  # only `assess` holds this; see RiskAssessment.__post_init__


@dataclass(frozen=True, slots=True)
class PortfolioState:
    """What is already at risk. There are no paper trades yet (Phase 12), so it is empty; the
    limits are enforced and tested so they are live the moment trades exist."""

    open_positions: int = 0
    realized_loss_today: Decimal = Decimal(0)


def current_portfolio_state() -> PortfolioState:
    return PortfolioState()


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    rules_action: SignalAction  # what the rule engine said
    action: SignalAction  # what the platform says after the veto
    plan: TradePlan | None
    size: PositionSize | None
    vetoes: list[Veto]
    kill_switch: bool
    limits: dict[str, str]
    _issued_by: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._issued_by is not _ISSUER:
            raise TypeError("a RiskAssessment can only be created by assess()")

    @property
    def actionable(self) -> bool:
        """BUY (with a plan and size) or SELL. HOLD and NO_TRADE mean do nothing."""
        return self.action in (SignalAction.BUY, SignalAction.SELL)

    def as_record(self) -> dict[str, Any]:
        """The JSON stored with the signal. A BUY always carries `plan` and `size`."""
        record: dict[str, Any] = {
            "assessed": True,
            "rules_action": self.rules_action.value,
            "kill_switch": self.kill_switch,
            "vetoes": [{"code": v.code, "text": v.text} for v in self.vetoes],
            "limits": self.limits,
        }
        if self.plan is not None:
            record["plan"] = {
                "side": self.plan.side,
                "entry": str(self.plan.entry),
                "stop": str(self.plan.stop),
                "target": str(self.plan.target),
                "risk_per_unit": str(self.plan.risk_per_unit),
                "reward_per_unit": str(self.plan.reward_per_unit),
                "risk_reward": str(self.plan.risk_reward),
            }
        if self.size is not None:
            record["size"] = {
                "quantity": str(self.size.quantity),
                "notional": str(self.size.notional),
                "risk_amount": str(self.size.risk_amount),
                "capital_share_pct": str(self.size.capital_share_pct),
                "limited_by": self.size.limited_by,
            }
        return record


def _limits_snapshot(limits: RiskLimits) -> dict[str, str]:
    return {name: str(value) for name, value in limits.model_dump(exclude={"admin_token"}).items()}


def assess(
    decision: Decision,
    *,
    symbol: str,
    entry: Decimal | None,
    atr: float | None,
    limits: RiskLimits,
    state: PortfolioState,
    kill_switch_on: bool,
) -> RiskAssessment:
    """Apply every risk rule to a rule-engine decision."""
    snapshot = _limits_snapshot(limits)

    def result(
        action: SignalAction,
        vetoes: list[Veto],
        plan: TradePlan | None = None,
        size: PositionSize | None = None,
    ) -> RiskAssessment:
        return RiskAssessment(
            rules_action=decision.action,
            action=action,
            plan=plan,
            size=size,
            vetoes=vetoes,
            kill_switch=kill_switch_on,
            limits=snapshot,
            _issued_by=_ISSUER,
        )

    if kill_switch_on:
        return result(
            SignalAction.NO_TRADE,
            [Veto("kill_switch", "The kill switch is on: no signal is actionable.")],
        )
    if decision.action is not SignalAction.BUY:
        return result(decision.action, [])  # nothing to open, so nothing to veto

    vetoes: list[Veto] = []
    if state.open_positions >= limits.max_open_positions:
        vetoes.append(
            Veto(
                "max_open_positions",
                f"{state.open_positions} positions are open; the limit is "
                f"{limits.max_open_positions}.",
            )
        )
    daily_limit = limits.capital * limits.max_daily_loss_pct / 100
    if state.realized_loss_today >= daily_limit:
        vetoes.append(
            Veto(
                "daily_loss_limit",
                f"Today's losses ({state.realized_loss_today}) reached the daily limit "
                f"({daily_limit}).",
            )
        )
    plan_or_veto = (
        plan_long(
            entry,
            atr,
            stop_atr_multiple=limits.stop_atr_multiple,
            target_atr_multiple=limits.target_atr_multiple,
            min_risk_reward=limits.min_risk_reward,
            max_stop_distance_pct=limits.max_stop_distance_pct,
        )
        if entry is not None
        else Veto("bad_entry", "There is no price to plan the trade from.")
    )
    if isinstance(plan_or_veto, Veto):
        vetoes.append(plan_or_veto)
        return result(SignalAction.NO_TRADE, vetoes)
    size_or_veto = position_size(
        capital=limits.capital,
        risk_pct=limits.risk_per_trade_pct,
        entry=plan_or_veto.entry,
        stop=plan_or_veto.stop,
        max_capital_share_pct=limits.max_capital_share_pct,
        step=quantity_step(symbol),
    )
    if isinstance(size_or_veto, Veto):
        vetoes.append(size_or_veto)
        return result(SignalAction.NO_TRADE, vetoes, plan=plan_or_veto)
    if vetoes:
        return result(SignalAction.NO_TRADE, vetoes, plan=plan_or_veto, size=size_or_veto)
    return result(SignalAction.BUY, [], plan=plan_or_veto, size=size_or_veto)
