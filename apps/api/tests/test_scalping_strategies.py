"""The scalping strategies: exact signals on hand-built features, causality, and registry."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np
import pytest

from app.analysis.features import FeatureTable, find_lookahead
from app.analysis.indicators import CandleSeries
from app.backtest.engine import BacktestConfig, run_backtest
from app.backtest.leakage import find_backtest_lookahead
from app.backtest.registry import STRATEGIES, resolve
from app.data.adapters.base import RawCandle
from app.data.models import SignalAction
from app.scalping.strategies import (
    _prior_extreme,
    ema_cross,
    range_breakout,
    scalp_features,
    vwap_pullback,
)

D = Decimal
T0 = datetime(2026, 1, 1, tzinfo=UTC)
BUY, SELL, HOLD = SignalAction.BUY, SignalAction.SELL, SignalAction.HOLD


def table(**series: list[float]) -> FeatureTable:
    n = max(len(v) for v in series.values())
    base = {"atr": [1.0] * n}
    base.update(series)
    return {k: np.array(v, dtype=np.float64) for k, v in base.items()}


def walk(n: int = 700, seed: int = 12, step_minutes: int = 5) -> list[RawCandle]:
    rng = np.random.default_rng(seed)
    price = 100.0
    out = []
    for i in range(n):
        price *= 1 + rng.normal(0, 0.003)
        out.append(
            RawCandle(
                T0 + timedelta(minutes=step_minutes * i),
                D(str(round(price, 4))),
                D(str(round(price * 1.002, 4))),
                D(str(round(price * 0.998, 4))),
                D(str(round(price, 4))),
                D(str(round(float(rng.uniform(1, 10)), 3))),
            )
        )
    return out


def test_ema_cross_buys_the_cross_up_sells_the_cross_down_and_otherwise_holds() -> None:
    up = ema_cross(table(ema_fast=[99.0, 101.0], ema_slow=[100.0, 100.0]))
    down = ema_cross(table(ema_fast=[101.0, 99.0], ema_slow=[100.0, 100.0]))
    flat = ema_cross(table(ema_fast=[101.0, 102.0], ema_slow=[100.0, 100.0]))  # already above

    assert (up.action, down.action, flat.action) == (BUY, SELL, HOLD)
    assert up.inputs["atr"] == 1.0 and up.reasons[0].code == "ema_cross_up"


def test_every_strategy_holds_while_warming_up() -> None:
    nan = float("nan")
    empty = table(
        close=[nan, nan],
        ema_fast=[nan, nan],
        ema_slow=[nan, nan],
        ema_trend=[nan, nan],
        vwap=[nan, nan],
        breakout_high=[nan, nan],
        exit_low=[nan, nan],
        volume_ratio=[nan, nan],
    )

    assert [f(empty).action for f in (ema_cross, vwap_pullback, range_breakout)] == [HOLD] * 3


def test_vwap_pullback_buys_a_reclaim_in_an_uptrend() -> None:
    features = table(
        close=[101.0, 100.5, 99.5, 99.8, 100.4],  # dipped under VWAP, then back above and rising
        vwap=[100.0] * 5,
        ema_fast=[101.0] * 5,
        ema_slow=[101.0] * 5,  # 21
        ema_trend=[100.0] * 5,  # 50: the 21 is above it, so uptrend
    )

    decision = vwap_pullback(features)

    assert decision.action is BUY and decision.reasons[0].code == "vwap_reclaim"


def test_vwap_pullback_needs_the_uptrend_and_the_dip() -> None:
    base = {"vwap": [100.0] * 5, "ema_fast": [101.0] * 5}
    no_trend = table(
        close=[101.0, 100.5, 99.5, 99.8, 100.4], ema_slow=[99.0] * 5, ema_trend=[100.0] * 5, **base
    )
    no_dip = table(
        close=[101.0, 101.2, 101.4, 101.6, 101.8],
        ema_slow=[101.0] * 5,
        ema_trend=[100.0] * 5,
        **base,
    )

    assert vwap_pullback(no_trend).action is not BUY
    assert vwap_pullback(no_dip).action is not BUY


def test_vwap_pullback_exits_when_vwap_is_lost_in_a_downtrend() -> None:
    features = table(
        close=[100.0, 99.0, 98.0, 97.0, 96.0],
        vwap=[100.0] * 5,
        ema_fast=[99.0] * 5,
        ema_slow=[99.5] * 5,
        ema_trend=[100.5] * 5,  # the fast average is under the trend average
    )

    assert vwap_pullback(features).action is SELL


def test_range_breakout_needs_the_new_high_and_the_volume() -> None:
    kwargs = {"exit_low": [95.0], "breakout_high": [100.0]}
    loud = range_breakout(table(close=[101.0], volume_ratio=[2.0], **kwargs))
    quiet = range_breakout(table(close=[101.0], volume_ratio=[1.0], **kwargs))
    broken = range_breakout(table(close=[94.0], volume_ratio=[1.0], **kwargs))
    inside = range_breakout(table(close=[98.0], volume_ratio=[2.0], **kwargs))

    assert (loud.action, quiet.action, broken.action, inside.action) == (BUY, HOLD, SELL, HOLD)


def test_the_prior_extreme_never_includes_the_current_candle() -> None:
    values = np.array([1.0, 2.0, 3.0, 10.0, 5.0, 4.0])

    highest = _prior_extreme(values, 3, "max")
    lowest = _prior_extreme(values, 3, "min")

    assert np.isnan(highest[:3]).all()
    assert list(highest[3:]) == [3.0, 10.0, 10.0]  # at index 3 the 10 itself is not yet counted
    assert list(lowest[3:]) == [1.0, 2.0, 3.0]
    assert len(highest) == len(values)


def test_scalp_features_never_use_a_later_candle() -> None:
    series = CandleSeries.from_candles(walk(300))

    assert find_lookahead(scalp_features, series, checkpoints=list(range(60, 300, 17))) == []


def test_decisions_are_deterministic() -> None:
    features = scalp_features(CandleSeries.from_candles(walk(200)))
    view = {k: v[:150] for k, v in features.items()}

    for strategy in (ema_cross, vwap_pullback, range_breakout):
        assert strategy(view) == strategy(view)


@pytest.mark.parametrize("name", ["scalp-ema-cross", "scalp-vwap-pullback", "scalp-breakout"])
def test_each_registered_strategy_runs_in_the_backtest_and_passes_the_leakage_check(
    name: str,
) -> None:
    data = walk(600)
    config = BacktestConfig("BTC/USDT", "5m", strategy=name, capital=D("10000"))

    result = run_backtest(data, config)  # picked by name from the registry
    chosen = resolve(name)
    leaks = find_backtest_lookahead(
        data, config, lambda _: chosen.decide, cuts=[250, 400, 550], features_fn=chosen.features
    )

    assert result.stats["decisions"] > 400
    assert result.equity[0] == D("10000")
    assert leaks == []


def test_the_registry_knows_all_four_strategies_and_refuses_unknown_names() -> None:
    assert set(STRATEGIES) == {
        "rules-v2",
        "scalp-ema-cross",
        "scalp-vwap-pullback",
        "scalp-breakout",
    }
    with pytest.raises(ValueError, match="scalp-breakout"):
        resolve("nope")
