"""Stop, target and risk-to-reward: exact decimal maths and the vetoes."""

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.risk.plan import TradePlan, Veto, plan_long, to_decimal

LIMITS = {
    "stop_atr_multiple": Decimal("1.5"),
    "target_atr_multiple": Decimal("3"),
    "min_risk_reward": Decimal("1.5"),
    "max_stop_distance_pct": Decimal("15"),
}


def test_a_normal_plan_has_exact_numbers() -> None:
    plan = plan_long(Decimal("100"), 2.0, **LIMITS)

    assert isinstance(plan, TradePlan)
    assert plan.entry == Decimal("100")
    assert plan.stop == Decimal("97")  # 100 - 1.5 * 2
    assert plan.target == Decimal("106")  # 100 + 3 * 2
    assert plan.risk_per_unit == Decimal("3") and plan.reward_per_unit == Decimal("6")
    assert plan.risk_reward == Decimal("2.00")


def test_floats_are_converted_without_binary_noise() -> None:
    plan = plan_long(Decimal("100"), 0.1, **LIMITS)

    assert isinstance(plan, TradePlan)
    assert plan.stop == Decimal("99.85")  # not 99.8499999999999943...
    assert to_decimal(0.1) == Decimal("0.1")


def test_below_the_minimum_risk_reward_is_vetoed() -> None:
    veto = plan_long(Decimal("100"), 2.0, **{**LIMITS, "min_risk_reward": Decimal("2.5")})

    assert isinstance(veto, Veto) and veto.code == "risk_reward_too_low"
    assert "2.00" in veto.text and "2.5" in veto.text


def test_a_stop_that_would_be_below_zero_is_vetoed() -> None:
    veto = plan_long(Decimal("1"), 5.0, **LIMITS)

    assert isinstance(veto, Veto) and veto.code == "stop_below_zero"


def test_a_stop_too_far_from_the_entry_is_vetoed() -> None:
    veto = plan_long(Decimal("100"), 12.0, **LIMITS)  # stop 18% away

    assert isinstance(veto, Veto) and veto.code == "stop_too_wide"


@pytest.mark.parametrize(
    "entry, atr, code",
    [
        (Decimal("0"), 1.0, "bad_entry"),
        (Decimal("-5"), 1.0, "bad_entry"),
        (Decimal("NaN"), 1.0, "bad_entry"),
        (Decimal("100"), None, "bad_atr"),
        (Decimal("100"), float("nan"), "bad_atr"),
        (Decimal("100"), float("inf"), "bad_atr"),
        (Decimal("100"), 0.0, "bad_atr"),
        (Decimal("100"), -1.0, "bad_atr"),
    ],
)
def test_bad_inputs_are_vetoed_not_crashed_on(entry: Decimal, atr: float | None, code: str) -> None:
    result = plan_long(entry, atr, **LIMITS)

    assert isinstance(result, Veto) and result.code == code


def test_a_tiny_atr_that_rounds_the_stop_onto_the_entry_is_vetoed() -> None:
    result = plan_long(Decimal("100"), 1e-12, **LIMITS)

    assert isinstance(result, Veto)


@given(
    entry=st.decimals(min_value=Decimal("0.0001"), max_value=Decimal("1000000"), places=6),
    atr=st.floats(min_value=1e-6, max_value=1e5, allow_nan=False, allow_infinity=False),
)
def test_every_plan_is_on_the_right_side_and_meets_the_minimum(entry: Decimal, atr: float) -> None:
    result = plan_long(entry, atr, **LIMITS)

    if isinstance(result, TradePlan):
        assert Decimal(0) < result.stop < result.entry < result.target
        assert result.risk_per_unit == result.entry - result.stop
        assert result.reward_per_unit == result.target - result.entry
        assert result.risk_reward >= LIMITS["min_risk_reward"]
        assert (result.risk_per_unit / result.entry * 100) <= LIMITS["max_stop_distance_pct"]
    else:
        assert result.code and result.text
