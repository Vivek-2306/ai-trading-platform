"""Metrics on series with known answers."""

import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np

from app.backtest.engine import BacktestConfig, BacktestResult, Trade
from app.backtest.metrics import (
    MIN_MEANINGFUL_TRADES,
    compute_metrics,
    max_drawdown_pct,
    sharpe_ratio,
)

D = Decimal
T0 = datetime(2026, 1, 1, tzinfo=UTC)


def trade(pnl: str, risk: str = "50", fees: str = "2", bars: int = 5) -> Trade:
    return Trade(
        entry_ts=T0,
        exit_ts=T0 + timedelta(hours=bars),
        entry_price=D(100),
        exit_price=D(101),
        quantity=D(1),
        pnl=D(pnl),
        fees=D(fees),
        risk_amount=D(risk),
        exit_reason="target",
        bars_held=bars,
    )


def result(trades: list[Trade], equity: list[str], timeframe: str = "1h") -> BacktestResult:
    return BacktestResult(
        config=BacktestConfig("BTC/USDT", timeframe),
        times=[T0 + timedelta(hours=i) for i in range(len(equity))],
        equity=[D(x) for x in equity],
        trades=trades,
        first_decision_index=50,
    )


def test_win_rate_profit_factor_expectancy_and_payoff_on_a_known_set() -> None:
    trades = [trade(p) for p in ("100", "-50", "100", "-50", "100")]

    m = compute_metrics(result(trades, ["1000"] * 5))

    assert (m.trades, m.wins, m.losses) == (5, 3, 2)
    assert m.win_rate_pct == 60.0
    assert m.profit_factor == 3.0  # 300 won / 100 lost
    assert m.expectancy == D("40")  # 200 / 5
    assert m.expectancy_r == 0.8  # (2 - 1 + 2 - 1 + 2) / 5 with a risk of 50 each
    assert m.avg_win == D("100") and m.avg_loss == D("-50") and m.payoff_ratio == 2.0
    assert m.net_pnl == D("200") and m.fees_paid == D("10") and m.gross_pnl == D("210")
    assert m.longest_losing_streak == 1


def test_longest_losing_streak() -> None:
    trades = [trade(p) for p in ("10", "-1", "-1", "-1", "10", "-1")]

    assert compute_metrics(result(trades, ["1000"] * 3)).longest_losing_streak == 3


def test_no_losses_means_no_profit_factor_not_infinity() -> None:
    m = compute_metrics(result([trade("10"), trade("20")], ["1000"] * 3))

    assert m.profit_factor is None and m.avg_loss is None and m.payoff_ratio is None
    assert m.win_rate_pct == 100.0


def test_max_drawdown_and_total_return() -> None:
    equity = ["1000", "1100", "1210", "1089", "1200"]

    m = compute_metrics(result([], equity))

    assert math.isclose(m.max_drawdown_pct, 10.0)  # from 1210 down to 1089
    assert math.isclose(m.total_return_pct, 20.0)
    assert m.initial_equity == D("1000") and m.final_equity == D("1200")


def test_drawdown_helper_edge_cases() -> None:
    assert max_drawdown_pct(np.array([])) == 0.0
    assert max_drawdown_pct(np.array([100.0, 110.0, 120.0])) == 0.0  # only going up
    assert math.isclose(max_drawdown_pct(np.array([100.0, 50.0, 100.0, 80.0])), 50.0)


def test_sharpe_matches_a_hand_computed_value() -> None:
    equity = np.array([100.0, 101.0, 100.5, 102.0, 103.0])
    returns = equity[1:] / equity[:-1] - 1
    expected = returns.mean() / returns.std(ddof=1) * math.sqrt(365)

    assert math.isclose(sharpe_ratio(equity, 365.0) or 0.0, expected)


def test_sharpe_is_none_without_spread_or_data() -> None:
    assert sharpe_ratio(np.array([100.0, 100.0, 100.0, 100.0]), 365.0) is None
    assert sharpe_ratio(np.array([100.0, 101.0]), 365.0) is None


def test_exposure_is_the_share_of_candles_in_a_position() -> None:
    m = compute_metrics(result([trade("10", bars=10), trade("10", bars=10)], ["1000"] * 100))

    assert m.exposure_pct == 20.0
    assert m.avg_bars_held == 10.0


def test_too_few_trades_carries_a_warning() -> None:
    few = compute_metrics(result([trade("10")] * 5, ["1000"] * 5))
    none = compute_metrics(result([], ["1000"] * 5))
    enough = compute_metrics(result([trade("10")] * MIN_MEANINGFUL_TRADES, ["1000"] * 5))

    assert "Only 5 trades" in few.warnings[0] and "noise" in few.warnings[0]
    assert none.warnings == ["No trades: there is nothing to measure."]
    assert none.win_rate_pct is None and none.expectancy is None
    assert enough.warnings == []


def test_to_dict_is_json_friendly() -> None:
    import json

    m = compute_metrics(result([trade("100"), trade("-50")], ["1000", "1100", "1050"]))

    data = m.to_dict()

    assert json.loads(json.dumps(data)) == data
    assert data["net_pnl"] == "50" and data["trades"] == 2
    assert isinstance(data["win_rate_pct"], float) and isinstance(data["initial_equity"], str)


def test_the_timeframe_sets_the_annualisation() -> None:
    equity = ["1000", "1010", "1005", "1020", "1030"]

    hourly = compute_metrics(result([], equity, "1h")).sharpe
    daily = compute_metrics(result([], equity, "1d")).sharpe

    assert hourly is not None and daily is not None
    assert math.isclose(hourly / daily, math.sqrt(8760 / 365))
