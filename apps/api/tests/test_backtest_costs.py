"""Fee tiers and the maker/taker split in the engine."""

from decimal import Decimal

import pytest

from app.backtest.costs import TIERS, round_trip_cost_bps, tier
from app.backtest.engine import BacktestConfig, BacktestResult, Trade, run_backtest
from app.backtest.runner import config_from_dict
from tests.test_backtest_engine import BUY, candles, cfg, script

D = Decimal


def test_tiers_have_named_maker_and_taker_rates() -> None:
    regular = tier("binance_regular")

    assert (regular.maker_pct, regular.taker_pct) == (D("0.10"), D("0.10"))
    assert tier("binance_bnb").taker_pct < regular.taker_pct  # the BNB discount
    assert tier("optimistic_bound").maker_pct == 0
    assert all(t.note for t in TIERS.values())  # every assumption is written down


def test_an_unknown_tier_says_which_exist() -> None:
    with pytest.raises(ValueError, match="binance_regular"):
        tier("nope")


def test_round_trip_cost_in_basis_points() -> None:
    # Taker both ways: 10 + 5 on entry, 10 + 5 on exit = 30 bps.
    assert round_trip_cost_bps(D("0.1"), None, D("5"), exit_by_target=False) == D("30")
    # A maker exit at the target skips the exit slippage and pays the maker fee instead.
    assert round_trip_cost_bps(D("0.1"), D("0.02"), D("5"), exit_by_target=True) == D("17")


def test_a_target_exit_pays_the_maker_fee_but_a_stop_still_pays_taker() -> None:
    target_data = candles(c62={"high": "108", "low": "100.5", "close": "107"})
    stop_data = candles(c62={"high": "100.4", "low": "95", "close": "96"})
    config = cfg(fee_pct=D("0.1"), maker_fee_pct=D("0.02"), slippage_bps=D("0"))

    hit = run_backtest(target_data, config, script({60: BUY})).trades[0]
    stopped = run_backtest(stop_data, config, script({60: BUY})).trades[0]

    assert hit.exit_reason == "target"
    assert hit.fees == hit.quantity * hit.entry_price * D("0.001") + (
        hit.quantity * hit.exit_price * D("0.0002")
    )
    assert stopped.exit_reason == "stop"
    assert stopped.fees == stopped.quantity * (stopped.entry_price + stopped.exit_price) * D(
        "0.001"
    )


def test_without_a_maker_rate_every_fill_pays_the_same_fee_as_before() -> None:
    data = candles(c62={"high": "108", "low": "100.5", "close": "107"})

    old_style = run_backtest(data, cfg(fee_pct=D("0.1")), script({60: BUY})).trades[0]

    assert old_style.fees == old_style.quantity * (
        old_style.entry_price + old_style.exit_price
    ) * D("0.001")


def test_the_maker_rate_changes_the_hash_and_survives_the_stored_round_trip() -> None:
    plain = BacktestConfig("BTC/USDT", "5m")
    with_maker = BacktestConfig("BTC/USDT", "5m", maker_fee_pct=D("0.02"))

    assert plain.config_hash() != with_maker.config_hash()
    assert config_from_dict(with_maker.to_dict()) == with_maker
    assert config_from_dict(plain.to_dict()) == plain  # a missing maker rate stays missing


def test_a_negative_maker_fee_is_refused() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        BacktestConfig("BTC/USDT", "5m", maker_fee_pct=D("-0.01"))


def _result(trades: list[Trade], days: int = 10) -> BacktestResult:
    from datetime import timedelta

    from tests.test_backtest_metrics import result as make_result

    out = make_result(trades, ["1000"] * 3)
    out.times = [out.times[0], out.times[1], out.times[0] + timedelta(days=days)]
    return out


def test_cost_drag_splits_gross_fees_and_net_and_shows_the_edge_per_trade() -> None:
    from app.backtest.costs import cost_drag
    from tests.test_backtest_metrics import trade

    # Two trades of 1 unit at entry 100: net +10 and -6, fees 2 each (gross +12 and -4).
    result = _result([trade("10", fees="2"), trade("-6", fees="2")], days=2)

    drag = cost_drag(result)

    assert drag["trades"] == 2 and drag["trades_per_day"] == 1.0
    assert drag["gross_pnl"] == "8" and drag["fees_paid"] == "4" and drag["net_pnl"] == "4"
    assert drag["fee_share_of_gross_pct"] == 50.0  # fees ate half of what the moves made
    assert drag["avg_gross_bps_per_trade"] == 400.0  # 8 / 200 notional
    assert drag["avg_fee_bps_per_trade"] == 200.0
    assert "400.0 bps" in str(drag["verdict"])


def test_when_the_moves_lose_money_before_fees_costs_are_not_blamed() -> None:
    from app.backtest.costs import cost_drag
    from tests.test_backtest_metrics import trade

    result = _result([trade("-10", fees="1"), trade("-5", fees="1")])

    drag = cost_drag(result)

    assert drag["fee_share_of_gross_pct"] is None
    assert "signals are" in str(drag["verdict"])


def test_cost_drag_with_no_trades_and_json_safety() -> None:
    import json

    from app.backtest.costs import cost_drag
    from tests.test_backtest_metrics import result as make_result
    from tests.test_backtest_metrics import trade

    assert cost_drag(make_result([], ["1000"] * 3))["trades"] == 0
    full = cost_drag(_result([trade("10")] * 3))
    assert json.loads(json.dumps(full)) == full
    assert full["exit_reasons"] == {"target": 3}
