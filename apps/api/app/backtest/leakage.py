"""Catching look-ahead in a backtest.

A strategy must decide the same way at candle t whether or not later candles exist. The check
runs the backtest on the full history and again on histories cut off earlier, and compares:
every decision made before the cut must be identical, and every trade closed before the cut
must be identical. A strategy that peeks at the future (its own copy of the data, a shifted
array, an index off by one) decides differently when the future is missing, and is caught.

Strategies are passed as FACTORIES that build the strategy from the candles it is given, so
the cut history is what the strategy sees. A strategy that smuggles in the full data some other
way cannot be caught by any black-box check: keep strategies pure functions of the features.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.backtest.engine import (
    BacktestConfig,
    BacktestResult,
    Strategy,
    default_strategy,
    run_backtest,
)
from app.data.adapters.base import RawCandle

StrategyFactory = Callable[[list[RawCandle]], Strategy]


@dataclass(frozen=True, slots=True)
class Leak:
    cut: int  # the history was cut to this many candles
    index: int  # the candle whose decision (or trade) changed
    detail: str


def real_rules(_: list[RawCandle]) -> Strategy:
    return default_strategy


def find_backtest_lookahead(
    candles: list[RawCandle],
    config: BacktestConfig,
    make_strategy: StrategyFactory = real_rules,
    cuts: Sequence[int] | None = None,
) -> list[Leak]:
    """Empty list = no look-ahead found at the chosen cut points."""
    ordered = sorted(candles, key=lambda c: c.ts)
    n = len(ordered)
    full = run_backtest(ordered, config, make_strategy(ordered))
    full_decisions = dict(full.decisions)
    points = list(cuts) if cuts is not None else [n * k // 5 for k in range(2, 5)]
    leaks: list[Leak] = []
    for cut in points:
        head = ordered[:cut]
        # Ask at the last candle too: that is where a strategy that peeks one candle ahead has
        # nothing to peek at, and so decides differently from the full run.
        short = run_backtest(head, config, make_strategy(head), ask_at_last=True)
        for index, action in short.decisions:
            if index in full_decisions and full_decisions[index] != action:
                leaks.append(
                    Leak(
                        cut,
                        index,
                        f"decided {action} with {cut} candles, "
                        f"{full_decisions.get(index)} with {n}",
                    )
                )
        leaks.extend(_trade_leaks(cut, short, full))
    return leaks


def _trade_leaks(cut: int, short: BacktestResult, full: BacktestResult) -> list[Leak]:
    last_time = short.times[-1]
    # A trade that was closed by the end-of-data rule in the short run is cut by definition.
    settled = [t for t in short.trades if t.exit_reason != "end_of_data"]
    reference = {(t.entry_ts, t.exit_ts, t.entry_price, t.exit_price) for t in full.trades}
    leaks = []
    for trade in settled:
        key = (trade.entry_ts, trade.exit_ts, trade.entry_price, trade.exit_price)
        if trade.exit_ts < last_time and key not in reference:
            leaks.append(
                Leak(cut, 0, f"trade {trade.entry_ts.isoformat()} differs in the full run")
            )
    return leaks
