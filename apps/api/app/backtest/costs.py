"""Trading costs: fee tiers, and where the money goes.

Spot exchanges charge a fee on every fill, lower for orders that rest in the book and add
liquidity (maker) than for orders that take liquidity (taker). In the backtest, entries, stop
exits, signal exits and the final close are market orders (taker, plus slippage); a target is a
resting limit order (maker, no slippage).

The tiers below are ILLUSTRATIVE, written from Binance's published spot schedule as I know it.
Fee schedules change and depend on your 30-day volume and on paying with BNB: check the current
schedule on the exchange before trusting a conclusion that depends on a tier. The last tier is a
deliberately optimistic bound ("what if costs were almost free?"), not something to expect.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

D = Decimal

if TYPE_CHECKING:
    from app.backtest.engine import BacktestResult


@dataclass(frozen=True, slots=True)
class FeeTier:
    name: str
    maker_pct: Decimal
    taker_pct: Decimal
    note: str


TIERS: dict[str, FeeTier] = {
    t.name: t
    for t in (
        FeeTier("binance_regular", D("0.10"), D("0.10"), "Standard spot rate, no discount."),
        FeeTier("binance_bnb", D("0.075"), D("0.075"), "Paying fees in BNB takes 25% off."),
        FeeTier("binance_vip1", D("0.09"), D("0.10"), "Illustrative higher-volume tier."),
        FeeTier(
            "optimistic_bound",
            D("0.00"),
            D("0.02"),
            "NOT a real tier: a best-case bound to see whether costs alone explain a failure.",
        ),
    )
}


def tier(name: str) -> FeeTier:
    try:
        return TIERS[name]
    except KeyError:
        raise ValueError(f"unknown fee tier {name!r}; choose from {sorted(TIERS)}") from None


def round_trip_cost_bps(
    taker_pct: Decimal, maker_pct: Decimal | None, slippage_bps: Decimal, *, exit_by_target: bool
) -> Decimal:
    """What one trade costs, in basis points of its notional: a taker entry (fee + slippage),
    then either a maker exit at the target (fee only) or a taker exit (fee + slippage)."""
    entry = taker_pct * 100 + slippage_bps
    if exit_by_target and maker_pct is not None:
        return entry + maker_pct * 100
    return entry + taker_pct * 100 + slippage_bps


def cost_drag(result: "BacktestResult") -> dict[str, object]:
    """Where a run's money went: how often it traded, what the moves were worth before fees,
    what fees took, and how big the average move was next to what one trade costs.

    "Gross" is after slippage (the fill prices already include it) and before fees. When gross
    is already negative, costs are not what sank the strategy: the signals were wrong.
    """
    trades = result.trades
    if not trades:
        return {"trades": 0, "verdict": "No trades, so there are no costs to analyse."}
    notional = sum((t.quantity * t.entry_price for t in trades), D(0))
    fees = sum((t.fees for t in trades), D(0))
    net = sum((t.pnl for t in trades), D(0))
    gross = net + fees
    days = max((result.times[-1] - result.times[0]).total_seconds() / 86_400, 1 / 24)
    reasons: dict[str, int] = {}
    for t in trades:
        reasons[t.exit_reason] = reasons.get(t.exit_reason, 0) + 1
    gross_bps = float(gross / notional * 10_000)
    fee_bps = float(fees / notional * 10_000)
    slippage_bps = float(result.config.slippage_bps)
    market_exit_share = 1 - reasons.get("target", 0) / len(trades)
    slippage_round_trip = slippage_bps * (1 + market_exit_share)  # an estimate: entry + exits
    if gross <= 0:
        verdict = (
            f"The moves lose money before fees ({gross_bps:.1f} bps per trade): costs are not "
            "the main problem, the signals are."
        )
    else:
        verdict = (
            f"Average move before fees: {gross_bps:.1f} bps per trade; fees take {fee_bps:.1f} bps"
            f" and slippage about {slippage_round_trip:.1f} bps, leaving "
            f"{gross_bps - fee_bps:.1f} bps before counting slippage's effect on price."
        )
    return {
        "trades": len(trades),
        "trades_per_day": round(len(trades) / days, 2),
        "gross_pnl": format(gross, "f"),
        "fees_paid": format(fees, "f"),
        "net_pnl": format(net, "f"),
        "fee_share_of_gross_pct": round(float(fees / gross * 100), 1) if gross > 0 else None,
        "avg_notional": format(notional / len(trades), "f"),
        "avg_gross_bps_per_trade": round(gross_bps, 2),
        "avg_fee_bps_per_trade": round(fee_bps, 2),
        "estimated_slippage_bps_round_trip": round(slippage_round_trip, 2),
        "exit_reasons": reasons,
        "verdict": verdict,
    }
