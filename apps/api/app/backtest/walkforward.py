"""Run the engine over walk-forward windows of the tuning region, and judge the locked period.

`rules-v2` has no fitted parameters, so a walk-forward run here measures CONSISTENCY: does the
strategy behave similarly across different stretches of history (bull, bear, sideways), or did
one lucky period carry the total? When models arrive (Phase 10), the train window is what they
are fitted on and the test window is what they are judged on.

Everything here receives a `Splits` and only reads `splits.tuning`; the locked candles are
reachable only through `judge_oos`, which unlocks them for one configuration.
"""

from dataclasses import dataclass

from app.analysis.features import MIN_CANDLES
from app.backtest.engine import (
    BacktestConfig,
    BacktestResult,
    Strategy,
    default_strategy,
    run_backtest,
)
from app.backtest.splits import Splits, Window, candles_for, walk_forward_windows


@dataclass(frozen=True, slots=True)
class WindowResult:
    window: Window
    result: BacktestResult


def walk_forward(
    splits: Splits,
    config: BacktestConfig,
    *,
    train_size: int,
    test_size: int,
    step: int | None = None,
    strategy: Strategy = default_strategy,
) -> list[WindowResult]:
    """One backtest per test window, using candles only from the tuning region."""
    tuning = splits.tuning
    results = []
    for window in walk_forward_windows(len(tuning), train_size, test_size, step):
        feed = candles_for(window.test, tuning)
        results.append(WindowResult(window, run_backtest(feed, config, strategy)))
    return results


def run_on_tuning(
    splits: Splits, config: BacktestConfig, strategy: Strategy = default_strategy
) -> BacktestResult:
    """The whole tuning region in one run (the number you may tune against)."""
    return run_backtest(splits.tuning, config, strategy)


def judge_oos(
    splits: Splits, config: BacktestConfig, strategy: Strategy = default_strategy
) -> BacktestResult:
    """Judge ONE configuration on the locked period. Refused if another one already was.

    The indicators need history before the first locked candle; that comes from the end of the
    tuning region (earlier data, so nothing leaks backwards).
    """
    locked = splits.oos.unlock(config.config_hash())
    feed = splits.tuning[-MIN_CANDLES:] + locked
    return run_backtest(feed, config, strategy)
