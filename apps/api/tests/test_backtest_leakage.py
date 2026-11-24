"""A strategy that peeks at the future must be caught, and the real rules must pass."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np

from app.analysis.features import FeatureTable
from app.backtest.engine import BacktestConfig, Strategy, run_backtest
from app.backtest.leakage import find_backtest_lookahead, real_rules
from app.backtest.metrics import compute_metrics
from app.data.adapters.base import RawCandle
from app.data.models import SignalAction
from app.signals.rules import Decision, Reason
from tests.test_backtest_metrics import result, trade

D = Decimal
T0 = datetime(2026, 1, 1, tzinfo=UTC)
CONFIG = BacktestConfig("BTC/USDT", "1h", capital=D("10000"))


def walk(n: int = 500, seed: int = 8) -> list[RawCandle]:
    rng = np.random.default_rng(seed)
    price = 100.0
    out = []
    for i in range(n):
        price *= 1 + rng.normal(0.0001, 0.012)
        out.append(
            RawCandle(
                T0 + timedelta(hours=i),
                D(str(round(price, 4))),
                D(str(round(price * 1.004, 4))),
                D(str(round(price * 0.996, 4))),
                D(str(round(price, 4))),
                D(5),
            )
        )
    return out


def oracle(candles: list[RawCandle]) -> Strategy:
    """Cheats: after candle i it looks at candle i+1's close in its own copy of the data."""
    closes = [float(c.close) for c in candles]

    def strategy(view: FeatureTable) -> Decision:
        i = len(view["close"]) - 1
        atr = float(view["atr"][-1])
        action = SignalAction.HOLD
        if i + 1 < len(closes):  # the future exists in the oracle's copy
            if closes[i + 1] > closes[i] * 1.001:
                action = SignalAction.BUY
            elif closes[i + 1] < closes[i] * 0.999:
                action = SignalAction.SELL
        return Decision(action, D("0.9"), [Reason("oracle", "peeked", "info")], {"atr": atr})

    return strategy


def test_the_real_rules_pass_the_lookahead_check() -> None:
    assert find_backtest_lookahead(walk(), CONFIG, real_rules, cuts=[200, 300, 400]) == []


def test_a_strategy_that_peeks_one_candle_ahead_is_caught() -> None:
    leaks = find_backtest_lookahead(walk(), CONFIG, oracle, cuts=[200, 300, 400])

    assert leaks, "an oracle that reads the next candle must be flagged"
    assert {leak.cut for leak in leaks} == {200, 300, 400}
    assert all(leak.index == leak.cut - 1 for leak in leaks)  # it shows at the cut's last candle
    assert "decided" in leaks[0].detail


def test_changing_the_future_never_changes_the_past() -> None:
    data = walk()
    altered = list(data)
    for i in range(350, len(altered)):  # rewrite everything after candle 349
        c = altered[i]
        altered[i] = RawCandle(c.ts, c.open * 2, c.high * 2, c.low * 2, c.close * 2, c.volume)

    base = run_backtest(data, CONFIG)
    changed = run_backtest(altered, CONFIG)

    assert [d for d in base.decisions if d[0] < 349] == [d for d in changed.decisions if d[0] < 349]
    early = [t for t in base.trades if t.exit_ts < data[349].ts]
    assert early == [t for t in changed.trades if t.exit_ts < data[349].ts]
    assert base.equity[:349] == changed.equity[:349]


def test_ordinary_results_are_not_flagged() -> None:
    honest = compute_metrics(run_backtest(walk(), CONFIG))

    assert not any("Too good" in w for w in honest.warnings)


def test_the_too_good_flag_triggers_on_each_signal_and_not_on_small_samples() -> None:
    wins = [trade("100")] * 20 + [trade("-5")]
    assert any("Too good" in w for w in compute_metrics(result(wins, ["1000"] * 30)).warnings)

    tiny = compute_metrics(result([trade("100")] * 3, ["1000"] * 30))
    assert not any("Too good" in w for w in tiny.warnings)  # 3 trades: a different warning
