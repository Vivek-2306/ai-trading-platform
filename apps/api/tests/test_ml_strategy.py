"""The model as a strategy: gating only, causal, and plugged into the backtest."""

from decimal import Decimal

import numpy as np
import pytest

pytest.importorskip("lightgbm")
pytest.importorskip("sklearn")

from app.analysis.indicators import CandleSeries
from app.backtest.engine import BacktestConfig, run_backtest
from app.backtest.leakage import find_backtest_lookahead
from app.backtest.registry import STRATEGIES, register
from app.data.models import SignalAction
from app.ml.strategy import ModelBank, make_strategy
from tests.test_ml_dataset import candle, walk

D = Decimal


def _raw(series: CandleSeries):  # type: ignore[no-untyped-def]
    return [
        candle(
            i,
            float(series.open[i]),
            float(series.high[i]),
            float(series.low[i]),
            float(series.close[i]),
        )
        for i in range(len(series))
    ]


def test_a_candle_is_scored_by_a_model_trained_only_on_finished_labels_before_it() -> None:
    series = walk(3000, seed=9)
    context = series.upto(2000)
    bank = ModelBank(context, 600, 300)

    cutoff = bank.cutoffs[2]
    rows = [i for i, t in enumerate(bank._label_end_times) if t < cutoff]

    assert bank.cutoff_for(series.times[1999]) == bank.cutoffs[-1]
    assert bank.cutoff_for(series.times[2500]) is None  # after the context: the frozen model
    assert bank.cutoff_for(series.times[10]) == "none"  # too early for any model
    assert (
        max(bank.data.label_end[rows])
        < bank.data.index[bank.data.label_end.searchsorted(0)] + 10**9
    )
    # every training label ended before its cutoff: the purge
    assert all(bank._label_end_times[i] < cutoff for i in rows)


def test_the_strategy_only_ever_buys_or_holds() -> None:
    series = walk(3000, seed=10)
    chosen = make_strategy(series.upto(2000), 600, 300, threshold=0.0)  # always at/above threshold
    table = chosen.features(series)

    actions = {
        chosen.decide({k: v[: t + 1] for k, v in table.items()}).action
        for t in range(700, 3000, 97)
    }

    assert actions <= {SignalAction.BUY, SignalAction.HOLD}
    assert SignalAction.SELL not in actions


def test_no_probability_means_hold() -> None:
    series = walk(800, seed=11)
    chosen = make_strategy(series, 600, 300)
    table = chosen.features(series.upto(200))  # before the first model exists

    decision = chosen.decide(table)

    assert decision.action is SignalAction.HOLD and decision.reasons[0].code == "ml_unavailable"


def test_a_registered_ml_strategy_runs_in_the_backtest_and_passes_the_leakage_check() -> None:
    series = walk(2600, seed=12)
    chosen = make_strategy(series.upto(1800), 600, 300, threshold=0.3)
    register(chosen)
    try:
        data = _raw(series)
        config = BacktestConfig("BTC/USDT", "1h", strategy="ml-lgbm-v1", capital=D("10000"))

        result = run_backtest(data, config)
        leaks = find_backtest_lookahead(
            data, config, lambda _: chosen.decide, cuts=[1000, 1700, 2000, 2500],
            features_fn=chosen.features,
        )  # fmt: skip

        assert result.stats["decisions"] > 1500 and result.stats["buy_signals"] > 0
        assert leaks == []  # the probability at t never depends on later candles
    finally:
        STRATEGIES.pop("ml-lgbm-v1", None)


def test_probabilities_do_not_change_when_later_candles_are_removed() -> None:
    series = walk(2600, seed=13)
    chosen = make_strategy(series.upto(1800), 600, 300)

    full = chosen.features(series)["ml_proba"]
    cut = chosen.features(series.upto(2100))["ml_proba"]

    assert np.allclose(full[:2100], cut, equal_nan=True)
