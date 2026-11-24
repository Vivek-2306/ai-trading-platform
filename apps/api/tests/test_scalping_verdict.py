from app.scalping.verdict import Verdict, judge, strategy_goes_on

GOOD = {"trades": 80, "total_return_pct": 3.2, "profit_factor": 1.4}


def test_a_good_result_passes() -> None:
    assert judge(GOOD) == Verdict(True, [])


def test_each_rule_fails_on_its_own_and_says_why() -> None:
    assert "only 10 trades" in judge({**GOOD, "trades": 10}).failures[0]
    assert "not positive" in judge({**GOOD, "total_return_pct": -0.1}).failures[0]
    assert "profit factor 1.10" in judge({**GOOD, "profit_factor": 1.1}).failures[0]


def test_missing_metrics_never_pass() -> None:
    assert not judge({}).passed


def test_a_strategy_needs_both_instruments_on_the_same_timeframe() -> None:
    ok, bad = Verdict(True, []), Verdict(False, ["x"])

    assert strategy_goes_on({("BTC", "5m"): ok, ("ETH", "5m"): ok, ("BTC", "1m"): bad})
    assert not strategy_goes_on({("BTC", "5m"): ok, ("ETH", "5m"): bad})
    assert not strategy_goes_on({("BTC", "5m"): ok})  # one instrument is not enough


def test_no_losing_trades_is_not_a_failed_profit_factor() -> None:
    assert judge({"trades": 40, "total_return_pct": 2.0, "profit_factor": None}).passed
    assert not judge({"trades": 0, "total_return_pct": 0, "profit_factor": None}).passed
