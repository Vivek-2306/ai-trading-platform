"""Go / no-go for a scalping strategy, with the pass rules fixed before the results were read.

A combination passes only if its single out-of-sample judgement, net of costs, shows ALL of:
net return above zero, profit factor of at least 1.2, and at least 30 trades. A strategy moves
on to paper trading only if it passes on BOTH instruments for at least one timeframe (one lucky
instrument is not evidence). Passing would still only earn a walk-forward check and paper
trading, never live money.
"""

from dataclasses import dataclass
from typing import Any

MIN_TRADES = 30
MIN_PROFIT_FACTOR = 1.2


@dataclass(frozen=True, slots=True)
class Verdict:
    passed: bool
    failures: list[str]


def judge(metrics: dict[str, Any]) -> Verdict:
    failures: list[str] = []
    trades = int(metrics.get("trades") or 0)
    net = float(metrics.get("total_return_pct") or 0.0)
    raw_pf = metrics.get("profit_factor")
    # No losing trades at all stores no profit factor (it would be infinite): that is not a failure.
    pf = float("inf") if raw_pf is None and trades > 0 else float(raw_pf or 0.0)
    if trades < MIN_TRADES:
        failures.append(f"only {trades} trades (need {MIN_TRADES})")
    if net <= 0:
        failures.append(f"net return {net:.1f}% is not positive")
    if pf < MIN_PROFIT_FACTOR:
        failures.append(f"profit factor {pf:.2f} is under {MIN_PROFIT_FACTOR}")
    return Verdict(not failures, failures)


def strategy_goes_on(per_combo: dict[tuple[str, str], Verdict]) -> bool:
    """per_combo is keyed by (symbol, timeframe)."""
    timeframes = {tf for _, tf in per_combo}
    return any(
        all(v.passed for (_, t), v in per_combo.items() if t == tf)
        and len([1 for (_, t) in per_combo if t == tf]) >= 2
        for tf in timeframes
    )
