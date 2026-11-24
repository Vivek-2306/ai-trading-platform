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

D = Decimal


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
