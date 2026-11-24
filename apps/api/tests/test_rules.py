"""The rule engine: each outcome, each reason, and the guarantees that always hold."""

from decimal import Decimal

import numpy as np
import pytest

from app.analysis.features import FeatureTable, compute_features
from app.analysis.indicators import CandleSeries
from app.data.models import SignalAction
from app.signals.rules import RULE_VERSION, RuleConfig, evaluate

NEUTRAL = {
    "close": 100.0,
    "sma_fast": 100.0,
    "sma_slow": 100.0,
    "ema_fast": 100.0,
    "ema_slow": 100.0,
    "rsi": 50.0,
    "macd": 0.0,
    "macd_signal": 0.0,
    "macd_hist": 0.0,
    "atr": 1.0,
    "atr_percent": 1.0,
    "bb_upper": 102.0,
    "bb_middle": 100.0,
    "bb_lower": 98.0,
    "percent_b": 0.5,
    "vwap": 100.0,
}


def table(prev: dict[str, float] | None = None, **now: float) -> FeatureTable:
    """Two candles of features: the previous one and the newest."""
    before = {**NEUTRAL, **(prev or {})}
    after = {**NEUTRAL, **now}
    return {k: np.array([before[k], after[k]], dtype=np.float64) for k in NEUTRAL}


def codes(decision_reasons: list) -> set[str]:  # type: ignore[type-arg]
    return {r.code for r in decision_reasons}


def test_agreeing_bullish_rules_give_buy_with_reasons() -> None:
    decision = evaluate(
        table(
            {"macd_hist": 0.1},
            ema_fast=105.0,
            ema_slow=100.0,
            close=104.0,
            sma_slow=100.0,
            macd_hist=0.3,
            vwap=102.0,
        )
    )

    assert decision.action is SignalAction.BUY
    assert codes(decision.reasons) == {"trend_up", "above_sma", "macd_up", "above_vwap"}
    assert Decimal("0.55") <= decision.confidence <= Decimal(1)
    assert decision.rule_version == RULE_VERSION
    assert all(r.text for r in decision.reasons)


def test_agreeing_bearish_rules_give_sell() -> None:
    decision = evaluate(
        table(
            {"macd_hist": -0.1},
            ema_fast=95.0,
            ema_slow=100.0,
            close=96.0,
            sma_slow=100.0,
            macd_hist=-0.3,
            vwap=98.0,
        )
    )

    assert decision.action is SignalAction.SELL
    assert {"trend_down", "below_sma", "macd_down", "below_vwap"} <= codes(decision.reasons)


def test_conflicting_indicators_mean_no_trade() -> None:
    # An uptrend, but RSI is overbought, price is above the upper band and momentum is fading.
    decision = evaluate(
        table(
            {"macd_hist": 0.5},
            ema_fast=105.0,
            ema_slow=100.0,
            close=110.0,
            sma_slow=100.0,
            rsi=82.0,
            percent_b=1.1,
            macd_hist=0.2,
        )
    )

    assert decision.action is SignalAction.NO_TRADE
    assert "conflict" in codes(decision.reasons)
    assert decision.summary == "Conflicting indicators"


def test_not_enough_history_means_no_trade() -> None:
    values = table()
    values["sma_slow"] = np.array([np.nan, np.nan])

    decision = evaluate(values)

    assert decision.action is SignalAction.NO_TRADE
    assert codes(decision.reasons) == {"warming_up"}
    assert decision.confidence == Decimal("0.0000")


def test_extreme_volatility_means_no_trade() -> None:
    decision = evaluate(table(atr_percent=12.0, ema_fast=105.0, close=104.0))

    assert decision.action is SignalAction.NO_TRADE
    assert codes(decision.reasons) == {"volatility_extreme"}


def test_weak_agreement_means_no_trade_not_a_forced_signal() -> None:
    # Trend (2) + above average (1) reach the bar to act, but only 46% of the weight agrees.
    decision = evaluate(table(ema_fast=101.0, close=101.0, sma_slow=100.0))

    assert decision.action is SignalAction.NO_TRADE
    assert "low_confidence" in codes(decision.reasons)
    assert decision.confidence < Decimal("0.55")


def test_nothing_decisive_is_hold() -> None:
    decision = evaluate(table(close=100.5, sma_slow=100.0))

    assert decision.action is SignalAction.HOLD
    assert "no_edge" in codes(decision.reasons)


def test_a_missing_optional_indicator_does_not_break_the_decision() -> None:
    values = table(ema_fast=105.0, ema_slow=100.0, close=104.0, sma_slow=100.0, macd_hist=0.3)
    values["vwap"] = np.array([np.nan, np.nan])  # e.g. spot gold has no volume

    decision = evaluate(values)

    assert decision.action in {SignalAction.BUY, SignalAction.NO_TRADE}
    assert "above_vwap" not in codes(decision.reasons)


def test_config_changes_the_thresholds() -> None:
    values = table(ema_fast=101.0, close=101.0, sma_slow=100.0)

    lenient = evaluate(values, RuleConfig(min_confidence=0.4))

    assert lenient.action is SignalAction.BUY


def test_the_decision_is_deterministic_and_records_its_inputs() -> None:
    values = table(ema_fast=105.0, close=104.0, sma_slow=100.0, macd_hist=0.3)

    first, second = evaluate(values), evaluate(values)

    assert first == second
    assert first.inputs["close"] == 104.0
    assert first.inputs["rsi"] == 50.0


@pytest.mark.parametrize("seed", range(40))
def test_every_decision_is_valid_and_explained(seed: int) -> None:
    rng = np.random.default_rng(seed)
    values = {
        "close": rng.uniform(50, 150),
        "sma_fast": rng.uniform(50, 150),
        "sma_slow": rng.uniform(50, 150),
        "ema_fast": rng.uniform(50, 150),
        "ema_slow": rng.uniform(50, 150),
        "rsi": rng.uniform(0, 100),
        "macd": rng.normal(),
        "macd_signal": rng.normal(),
        "macd_hist": rng.normal(),
        "atr": rng.uniform(0.1, 5),
        "atr_percent": rng.uniform(0.1, 15),
        "bb_upper": 150.0,
        "bb_middle": 100.0,
        "bb_lower": 50.0,
        "percent_b": rng.uniform(-0.2, 1.2),
        "vwap": rng.uniform(50, 150),
    }
    prev = {k: float(rng.uniform(-1, 1)) if k == "macd_hist" else v for k, v in values.items()}

    decision = evaluate(table(prev, **values))

    assert decision.action in set(SignalAction)
    assert decision.reasons, "every decision must explain itself"
    assert Decimal(0) <= decision.confidence <= Decimal(1)
    if decision.action in (SignalAction.BUY, SignalAction.SELL):
        assert decision.confidence >= Decimal("0.55")
        side = "buy" if decision.action is SignalAction.BUY else "sell"
        assert any(r.direction == side for r in decision.reasons)


def test_works_on_real_features_end_to_end() -> None:
    from datetime import UTC, datetime, timedelta

    from app.data.adapters.base import RawCandle

    rng = np.random.default_rng(1)
    price = 100.0
    candles = []
    start = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(160):
        price *= 1 + rng.normal(0.001, 0.01)
        candles.append(
            RawCandle(
                start + timedelta(hours=i),
                Decimal(str(round(price, 4))),
                Decimal(str(round(price * 1.004, 4))),
                Decimal(str(round(price * 0.996, 4))),
                Decimal(str(round(price, 4))),
                Decimal("5"),
            )
        )

    decision = evaluate(compute_features(CandleSeries.from_candles(candles)))

    assert decision.action in set(SignalAction)
    assert decision.reasons
    assert decision.inputs["rsi"] is not None
