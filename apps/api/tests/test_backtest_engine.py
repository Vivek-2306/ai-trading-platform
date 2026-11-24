"""The backtest engine on hand-built candles, where every fill can be checked by arithmetic."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np
import pytest

from app.analysis.features import FeatureTable
from app.backtest.engine import BacktestConfig, BacktestResult, run_backtest
from app.data.adapters.base import RawCandle
from app.data.models import SignalAction
from app.signals.rules import Decision, Reason

D = Decimal
T0 = datetime(2026, 1, 1, tzinfo=UTC)
WARM = 60  # candles before the scripted part (more than the indicators' warm-up)


def candles(n: int = 90, **moves: dict[str, str]) -> list[RawCandle]:
    """Flat candles at 100 (range 99.5 to 100.5), with chosen candles replaced.
    `c70={"open": "101", ...}` replaces candle 70's fields."""
    out = []
    for i in range(n):
        fields = {"open": "100", "high": "100.5", "low": "99.5", "close": "100", "volume": "1"}
        fields.update(moves.get(f"c{i}", {}))
        out.append(
            RawCandle(
                T0 + timedelta(hours=i),
                D(fields["open"]),
                D(fields["high"]),
                D(fields["low"]),
                D(fields["close"]),
                D(fields["volume"]),
            )
        )
    return out


def script(plan: dict[int, SignalAction], atr: float = 2.0):  # type: ignore[no-untyped-def]
    """A strategy that decides `plan[i]` after candle i has closed, and nothing otherwise."""

    def strategy(view: FeatureTable) -> Decision:
        i = len(view["close"]) - 1
        action = plan.get(i, SignalAction.HOLD)
        return Decision(action, D("0.8"), [Reason("script", "scripted", "info")], {"atr": atr})

    return strategy


def cfg(**over: object) -> BacktestConfig:
    base: dict[str, object] = {
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "capital": D("10000"),
        "fee_pct": D("0.1"),
        "slippage_bps": D("5"),
    }
    base.update(over)
    return BacktestConfig(**base)  # type: ignore[arg-type]


BUY, SELL = SignalAction.BUY, SignalAction.SELL


def test_a_buy_fills_at_the_next_open_with_slippage_never_at_the_signal_close() -> None:
    data = candles(c61={"open": "101", "high": "101.5", "low": "100.5", "close": "101"})

    result = run_backtest(data, cfg(), script({60: BUY}))

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_ts == T0 + timedelta(hours=61)  # the candle AFTER the decision
    assert trade.entry_price == D("101") * (1 + D("5") / 10000)  # open 101 + 5 bps


def test_a_target_exit_fills_at_the_target_and_pnl_is_exact() -> None:
    data = candles(c62={"high": "108", "low": "100.5", "close": "107"})

    result = run_backtest(data, cfg(), script({60: BUY}))

    trade = result.trades[0]
    entry = D("100") * D("1.0005")  # open 100 plus 5 bps slippage
    target = (entry + D("3") * D("2")).quantize(D("0.00000001"), rounding="ROUND_DOWN")
    assert trade.exit_reason == "target" and trade.exit_price == target  # limit: no slippage
    entry_fee = trade.quantity * entry * D("0.001")
    exit_fee = trade.quantity * target * D("0.001")
    assert trade.pnl == trade.quantity * (target - entry) - entry_fee - exit_fee
    assert trade.fees == entry_fee + exit_fee
    assert trade.pnl > 0 and trade.exit_ts == T0 + timedelta(hours=62)


def test_a_stop_exit_fills_at_the_stop_with_slippage_against_you() -> None:
    data = candles(c62={"high": "100.4", "low": "95", "close": "96"})

    result = run_backtest(data, cfg(), script({60: BUY}))

    trade = result.trades[0]
    stop = trade.entry_price - D("3")  # 1.5 x ATR 2.0 below the entry fill
    assert trade.exit_reason == "stop"
    assert trade.exit_price == stop * (1 - D("5") / 10000)
    assert trade.pnl < 0
    # The loss is a little more than the 0.5% of capital that was risked: costs on top.
    assert abs(trade.pnl) > trade.risk_amount - D("0.01")


def test_a_candle_touching_both_stop_and_target_counts_as_the_stop() -> None:
    data = candles(c62={"high": "120", "low": "90", "close": "100"})

    result = run_backtest(data, cfg(), script({60: BUY}))

    assert result.trades[0].exit_reason == "stop"  # the cautious assumption


def test_a_gap_below_the_stop_fills_at_the_open_not_at_the_stop() -> None:
    data = candles(
        c62={"open": "90", "high": "91", "low": "89", "close": "90"},
    )

    result = run_backtest(data, cfg(), script({60: BUY}))

    trade = result.trades[0]
    assert trade.exit_reason == "stop"
    assert trade.exit_price == D("90") * (1 - D("5") / 10000)  # the open, worse than the stop


def test_a_sell_signal_exits_at_the_next_open() -> None:
    data = candles(c64={"open": "102", "high": "102.5", "low": "101.5", "close": "102"})

    result = run_backtest(data, cfg(), script({60: BUY, 63: SELL}))

    trade = result.trades[0]
    assert trade.exit_reason == "signal" and trade.exit_ts == T0 + timedelta(hours=64)
    assert trade.exit_price == D("102") * (1 - D("5") / 10000)


def test_an_open_position_is_closed_at_the_last_close() -> None:
    result = run_backtest(candles(), cfg(), script({60: BUY}))

    trade = result.trades[0]
    assert trade.exit_reason == "end_of_data" and trade.exit_ts == T0 + timedelta(hours=89)
    assert result.equity[-1] == D("10000") + sum(t.pnl for t in result.trades)


def test_latency_delays_the_fill() -> None:
    data = candles(c63={"open": "103", "high": "103.5", "low": "102.5", "close": "103"})

    result = run_backtest(data, cfg(latency_candles=2), script({60: BUY}))

    assert result.trades[0].entry_ts == T0 + timedelta(hours=63)  # decision at 60, +1, +2 latency
    assert result.trades[0].entry_price == D("103") * D("1.0005")


def test_with_no_costs_pnl_is_pure_price_difference() -> None:
    data = candles(c64={"open": "102", "high": "102.5", "low": "101.5", "close": "102"})

    result = run_backtest(
        data, cfg(fee_pct=D("0"), slippage_bps=D("0")), script({60: BUY, 63: SELL})
    )

    trade = result.trades[0]
    assert trade.fees == 0
    assert trade.pnl == trade.quantity * (D("102") - D("100"))


def test_costs_make_the_same_trade_worse() -> None:
    data = candles(c64={"open": "102", "high": "102.5", "low": "101.5", "close": "102"})
    plan = {60: BUY, 63: SELL}

    free = run_backtest(data, cfg(fee_pct=D("0"), slippage_bps=D("0")), script(plan))
    costly = run_backtest(data, cfg(), script(plan))

    assert costly.trades[0].pnl < free.trades[0].pnl


def test_position_size_follows_the_risk_engine() -> None:
    result = run_backtest(candles(), cfg(), script({60: BUY}))

    trade = result.trades[0]
    # 0.5% of 10,000 = 50 at risk; 3 per unit between entry and stop; BTC lot size 0.00001.
    assert trade.risk_amount <= D("50") and trade.risk_amount > D("49.9")
    assert trade.quantity % D("0.00001") == 0


def test_no_leverage_cash_never_goes_negative() -> None:
    # A huge risk budget would size more than cash allows; the engine cuts it to what cash pays.
    result = run_backtest(
        candles(),
        cfg(
            capital=D("1000"),
            risk_per_trade_pct=D("2"),
            max_capital_share_pct=D("100"),
            max_daily_loss_pct=D("5"),
        ),
        script({60: BUY}),
    )

    trade = result.trades[0]
    assert trade.quantity * trade.entry_price + trade.fees / 2 <= D("1000") + D("0.01")


def test_a_buy_the_risk_engine_vetoes_never_trades() -> None:
    result = run_backtest(candles(), cfg(), script({60: BUY}, atr=40.0))  # stop 60% away

    assert result.trades == []
    assert result.stats["buy_signals"] == 1 and result.stats["vetoed"] == 1


def test_the_daily_loss_limit_blocks_a_second_entry_the_same_day() -> None:
    data = candles(c62={"high": "100.4", "low": "95", "close": "96"})  # first trade stops out
    config = cfg(risk_per_trade_pct=D("0.05"), max_daily_loss_pct=D("0.05"))

    result = run_backtest(data, config, script({60: BUY, 64: BUY}))

    assert len(result.trades) == 1  # the stop-out used up the day's loss budget
    assert result.stats["vetoed"] == 1


def test_one_position_at_a_time() -> None:
    result = run_backtest(candles(), cfg(), script({60: BUY, 62: BUY, 64: BUY}))

    assert len(result.trades) == 1  # later BUYs are ignored while the position is open


def test_equity_starts_at_capital_and_ends_at_capital_plus_pnl() -> None:
    data = candles(c64={"open": "102", "high": "102.5", "low": "101.5", "close": "102"})

    result = run_backtest(data, cfg(), script({60: BUY, 63: SELL}))

    assert result.equity[0] == D("10000")
    assert len(result.equity) == len(data)
    assert result.equity[-1] == D("10000") + sum(t.pnl for t in result.trades)


def test_the_same_input_always_gives_the_same_result() -> None:
    data = candles(c64={"open": "102", "high": "102.5", "low": "101.5", "close": "102"})

    a = run_backtest(data, cfg(), script({60: BUY, 63: SELL}))
    b = run_backtest(list(reversed(data)), cfg(), script({60: BUY, 63: SELL}))  # order of input

    assert [t.to_dict() for t in a.trades] == [t.to_dict() for t in b.trades]
    assert a.equity == b.equity
    assert cfg().config_hash() == cfg().config_hash() != cfg(fee_pct=D("0.2")).config_hash()


def test_the_real_rules_run_end_to_end_on_a_random_walk() -> None:
    rng = np.random.default_rng(4)
    price = 100.0
    data = []
    for i in range(600):
        price *= 1 + rng.normal(0.0002, 0.01)
        data.append(
            RawCandle(
                T0 + timedelta(hours=i),
                D(str(round(price, 4))),
                D(str(round(price * 1.004, 4))),
                D(str(round(price * 0.996, 4))),
                D(str(round(price, 4))),
                D("5"),
            )
        )

    result: BacktestResult = run_backtest(data, cfg())

    assert result.stats["decisions"] > 400
    assert result.equity[0] == D("10000")
    assert result.equity[-1] == D("10000") + sum(t.pnl for t in result.trades)
    for trade in result.trades:  # every trade respected the sizing caps
        assert trade.risk_amount <= D("10000") * D("0.5") / 100 * 2  # compounding headroom


def test_too_few_candles_is_an_error_and_bad_config_is_refused() -> None:
    with pytest.raises(ValueError, match="at least"):
        run_backtest(candles(30), cfg())
    with pytest.raises(ValueError, match="cannot be negative"):
        cfg(fee_pct=D("-1"))
    with pytest.raises(ValueError, match="capital must be positive"):
        cfg(capital=D("0"))
