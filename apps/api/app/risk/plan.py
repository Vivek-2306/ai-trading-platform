"""Stop-loss, target and risk-to-reward for a long trade, from the entry price and the ATR.

All money maths here is `Decimal`. The ATR (average candle range) comes from the indicator
code as a float and is converted once on the way in. The platform is long-only spot, so the
stop is below the entry and the target above it. Stops are rounded away from the entry and
targets toward it, so rounding can only make a plan more cautious, never less.
"""

import math
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

PRICE_QUANTUM = Decimal("0.00000001")  # 8 decimal places


@dataclass(frozen=True, slots=True)
class TradePlan:
    side: str  # always "long" for now
    entry: Decimal
    stop: Decimal
    target: Decimal
    risk_per_unit: Decimal  # entry - stop: what one unit loses if the stop is hit
    reward_per_unit: Decimal  # target - entry
    risk_reward: Decimal  # reward_per_unit / risk_per_unit


@dataclass(frozen=True, slots=True)
class Veto:
    """A reason the risk engine refuses a trade."""

    code: str
    text: str


def to_decimal(value: float | Decimal) -> Decimal:
    """A float from analysis code as an exact decimal of its shortest repr (0.1 -> 0.1)."""
    return value if isinstance(value, Decimal) else Decimal(repr(float(value)))


def plan_long(
    entry: Decimal,
    atr: float | Decimal | None,
    *,
    stop_atr_multiple: Decimal,
    target_atr_multiple: Decimal,
    min_risk_reward: Decimal,
    max_stop_distance_pct: Decimal,
) -> TradePlan | Veto:
    """A plan for buying at `entry`, or the reason there should not be one."""
    if not entry.is_finite() or entry <= 0:
        return Veto("bad_entry", "The entry price is not a positive number.")
    if atr is None or (isinstance(atr, float) and not math.isfinite(atr)):
        return Veto("bad_atr", "The average candle range (ATR) is not available.")
    atr_value = to_decimal(atr)
    if not atr_value.is_finite() or atr_value <= 0:
        return Veto("bad_atr", "The average candle range (ATR) is zero or negative.")

    stop = (entry - stop_atr_multiple * atr_value).quantize(PRICE_QUANTUM, rounding=ROUND_DOWN)
    if stop <= 0:
        return Veto("stop_below_zero", "The stop-loss would be at or below zero: too volatile.")
    target = (entry + target_atr_multiple * atr_value).quantize(PRICE_QUANTUM, rounding=ROUND_DOWN)
    risk = entry - stop
    reward = target - entry
    if risk <= 0:
        return Veto("stop_not_below_entry", "The stop-loss is not below the entry price.")
    if reward <= 0:
        return Veto("target_not_above_entry", "The target is not above the entry price.")

    distance_pct = risk / entry * 100
    if distance_pct > max_stop_distance_pct:
        return Veto(
            "stop_too_wide",
            f"The stop-loss is {distance_pct:.1f}% below the entry; "
            f"the limit is {max_stop_distance_pct}%.",
        )
    ratio = (reward / risk).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    if ratio < min_risk_reward:
        return Veto(
            "risk_reward_too_low",
            f"Risk-to-reward is {ratio}, below the minimum of {min_risk_reward}.",
        )
    return TradePlan("long", entry, stop, target, risk, reward, ratio)
