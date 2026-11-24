"""Position size: risk a fixed fraction of capital between the entry and the stop.

quantity = (capital x risk%) / (entry - stop), then limited so the position never takes more
than `max_capital_share_pct` of capital, then rounded DOWN to the instrument's quantity step.
All `Decimal`. Rounding down means the real risk is never above the intended risk.
"""

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from app.risk.plan import Veto

# Smallest tradable amount per symbol (Binance spot lot sizes, rounded to a safe step).
QUANTITY_STEPS = {
    "BTC/USDT": Decimal("0.00001"),
    "ETH/USDT": Decimal("0.0001"),
    "PAXG/USDT": Decimal("0.0001"),
}
DEFAULT_STEP = Decimal("0.0001")


def quantity_step(symbol: str) -> Decimal:
    return QUANTITY_STEPS.get(symbol, DEFAULT_STEP)


@dataclass(frozen=True, slots=True)
class PositionSize:
    quantity: Decimal
    notional: Decimal  # quantity x entry
    risk_amount: Decimal  # quantity x (entry - stop): the loss if the stop is hit
    capital_share_pct: Decimal  # notional as a percent of capital
    limited_by: str  # "risk" or "capital_share": which limit set the size


def _round_down(value: Decimal, step: Decimal) -> Decimal:
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def position_size(
    *,
    capital: Decimal,
    risk_pct: Decimal,
    entry: Decimal,
    stop: Decimal,
    max_capital_share_pct: Decimal,
    step: Decimal,
) -> PositionSize | Veto:
    positive = (capital, risk_pct, entry, stop, max_capital_share_pct, step)
    if any(not value.is_finite() or value <= 0 for value in positive) or stop >= entry:
        return Veto("bad_sizing_input", "Capital, prices or limits are not usable for sizing.")

    by_risk = capital * risk_pct / 100 / (entry - stop)
    by_share = capital * max_capital_share_pct / 100 / entry
    raw, limited_by = (by_risk, "risk") if by_risk <= by_share else (by_share, "capital_share")
    quantity = _round_down(raw, step)
    if quantity <= 0:
        return Veto(
            "size_too_small",
            "The allowed size is smaller than the smallest tradable amount.",
        )
    notional = quantity * entry
    return PositionSize(
        quantity=quantity,
        notional=notional,
        risk_amount=quantity * (entry - stop),
        capital_share_pct=(notional / capital * 100).quantize(Decimal("0.01"), rounding=ROUND_DOWN),
        limited_by=limited_by,
    )
