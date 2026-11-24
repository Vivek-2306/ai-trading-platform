"""Buy-and-hold on candles where the answer can be worked out by hand."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.analysis.features import MIN_CANDLES
from app.backtest.benchmark import compare, run_buy_and_hold
from app.backtest.engine import BacktestConfig, run_backtest
from app.data.adapters.base import RawCandle
from tests.test_backtest_engine import BUY, SELL, script

D = Decimal
T0 = datetime(2026, 1, 1, tzinfo=UTC)


def rising(n: int = 90, start: float = 100.0, step: float = 1.0) -> list[RawCandle]:
    out = []
    for i in range(n):
        price = D(str(start + step * i))
        out.append(
            RawCandle(
                T0 + timedelta(hours=i), price, price + D("0.5"), price - D("0.5"), price, D(1)
            )
        )
    return out


def cfg(**over: object) -> BacktestConfig:
    base: dict[str, object] = {"symbol": "BTC/USDT", "timeframe": "1h", "capital": D("10000")}
    base.update(over)
    return BacktestConfig(**base)  # type: ignore[arg-type]


def test_buy_and_hold_with_no_costs_is_the_price_change() -> None:
    data = rising()  # open at index 51 = 151, last close = 189
    free = cfg(fee_pct=D("0"), slippage_bps=D("0"))

    result = run_buy_and_hold(data, free)

    trade = result.trades[0]
    assert trade.entry_ts == data[MIN_CANDLES + 1].ts and trade.entry_price == D("151")
    assert trade.exit_price == D("189") and trade.exit_reason == "end_of_data"
    gain = trade.quantity * (D("189") - D("151"))
    assert result.equity[-1] == D("10000") + gain
    assert len(result.equity) == len(data) and result.equity[0] == D("10000")


def test_costs_reduce_buy_and_hold_and_cannot_overspend() -> None:
    data = rising()

    free = run_buy_and_hold(data, cfg(fee_pct=D("0"), slippage_bps=D("0")))
    costly = run_buy_and_hold(data, cfg(fee_pct=D("0.1"), slippage_bps=D("5")))

    assert costly.equity[-1] < free.equity[-1]
    trade = costly.trades[0]
    assert trade.quantity * trade.entry_price * D("1.001") <= D("10000")  # price plus the entry fee


def test_the_benchmark_uses_the_same_fees_as_the_strategy() -> None:
    data = rising()
    config = cfg()

    strategy = run_backtest(data, config, script({60: BUY, 70: SELL}))
    benchmark = run_buy_and_hold(data, config)

    assert strategy.config == benchmark.config  # one config, so both sides pay the same costs
    assert len(strategy.equity) == len(benchmark.equity)


def test_a_strategy_that_trades_a_rising_market_lags_buy_and_hold() -> None:
    data = rising()
    config = cfg()

    comparison = compare(
        run_backtest(data, config, script({60: BUY, 70: SELL})), run_buy_and_hold(data, config)
    )

    assert comparison.benchmark.total_return_pct > comparison.strategy.total_return_pct
    assert not comparison.beat_on_return and comparison.excess_return_pct < 0
    assert comparison.verdict.startswith(("Lagged", "Did not beat"))
    assert "Only 1 trades" in comparison.verdict  # the small-sample warning travels with it


def test_a_smaller_drawdown_is_not_oversold_when_the_strategy_was_mostly_out() -> None:
    data = rising(90, start=200.0, step=-1.0)
    config = cfg()

    comparison = compare(
        run_backtest(data, config, script({60: BUY, 61: SELL})), run_buy_and_hold(data, config)
    )

    assert "in the market only" in comparison.verdict or comparison.verdict.startswith("Beat")


def test_a_strategy_that_dodges_a_crash_beats_buy_and_hold() -> None:
    data = rising(90, start=200.0, step=-1.0)  # a steady fall
    config = cfg()

    comparison = compare(run_backtest(data, config, script({})), run_buy_and_hold(data, config))

    assert comparison.strategy.total_return_pct == 0.0  # it never traded: cash kept its value
    assert comparison.benchmark.total_return_pct < 0
    assert comparison.beat_on_return and comparison.beat_on_drawdown
    # Never trading is staying out, not skill, and the verdict must say so.
    assert comparison.verdict.startswith("The strategy never traded")
    assert "not skill" in comparison.verdict


def test_the_comparison_is_json_ready() -> None:
    import json

    data = rising()
    config = cfg()
    out = compare(run_backtest(data, config, script({})), run_buy_and_hold(data, config)).to_dict()

    assert json.loads(json.dumps(out)) == out
    assert {"excess_return_pct", "verdict", "beat_on_return", "benchmark"} <= set(out)


def test_too_little_data_is_refused() -> None:
    with pytest.raises(ValueError, match="at least"):
        run_buy_and_hold(rising(20), cfg())
