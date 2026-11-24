"""Position sizing: exact numbers, and properties that must hold for every input."""

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.risk.plan import Veto
from app.risk.sizing import PositionSize, position_size, quantity_step

D = Decimal


def size(**over: Decimal) -> PositionSize | Veto:
    args = {
        "capital": D("10000"),
        "risk_pct": D("1"),
        "entry": D("100"),
        "stop": D("97"),
        "max_capital_share_pct": D("50"),
        "step": D("0.01"),
    }
    args.update(over)
    return position_size(**args)


def test_risks_the_chosen_fraction_between_entry_and_stop() -> None:
    result = size()

    assert isinstance(result, PositionSize)
    assert result.quantity == D("33.33")  # 100 risk / 3 per unit = 33.33..., rounded down
    assert result.risk_amount == D("99.99")  # never above the 100 intended
    assert result.notional == D("3333.00")
    assert result.capital_share_pct == D("33.33")
    assert result.limited_by == "risk"


def test_the_capital_share_cap_can_be_the_binding_limit() -> None:
    result = size(stop=D("99"), max_capital_share_pct=D("10"))  # risk allows 100 units = 10000

    assert isinstance(result, PositionSize)
    assert result.quantity == D("10")  # 10% of 10,000 / 100
    assert result.notional == D("1000")
    assert result.limited_by == "capital_share"


def test_rounds_down_to_the_step_never_up() -> None:
    result = size(step=D("5"))

    assert isinstance(result, PositionSize) and result.quantity == D("30")


def test_a_size_below_the_smallest_lot_is_vetoed() -> None:
    result = size(capital=D("10"), step=D("1"))

    assert isinstance(result, Veto) and result.code == "size_too_small"


@pytest.mark.parametrize(
    "over",
    [
        {"capital": D("0")},
        {"capital": D("-1")},
        {"risk_pct": D("0")},
        {"entry": D("0")},
        {"stop": D("100")},  # stop not below entry
        {"stop": D("101")},
        {"stop": D("0")},
        {"step": D("0")},
        {"capital": D("NaN")},
        {"max_capital_share_pct": D("Infinity")},
    ],
)
def test_unusable_inputs_are_vetoed(over: dict[str, Decimal]) -> None:
    result = size(**over)

    assert isinstance(result, Veto) and result.code == "bad_sizing_input"


def test_known_symbols_have_lot_sizes() -> None:
    assert quantity_step("BTC/USDT") == D("0.00001")
    assert quantity_step("UNKNOWN/USDT") == D("0.0001")


@given(
    capital=st.decimals(min_value=D("1"), max_value=D("10000000"), places=2),
    risk_pct=st.decimals(min_value=D("0.01"), max_value=D("2"), places=2),
    entry=st.decimals(min_value=D("0.01"), max_value=D("500000"), places=4),
    stop_fraction=st.decimals(min_value=D("0.001"), max_value=D("0.9"), places=3),
    share=st.decimals(min_value=D("1"), max_value=D("100"), places=1),
    step=st.sampled_from([D("0.00001"), D("0.0001"), D("0.01"), D("1")]),
)
def test_size_never_exceeds_either_cap_and_always_fits_the_step(
    capital: Decimal,
    risk_pct: Decimal,
    entry: Decimal,
    stop_fraction: Decimal,
    share: Decimal,
    step: Decimal,
) -> None:
    stop = entry * (1 - stop_fraction)
    result = position_size(
        capital=capital,
        risk_pct=risk_pct,
        entry=entry,
        stop=stop,
        max_capital_share_pct=share,
        step=step,
    )
    if isinstance(result, Veto):
        return

    assert result.quantity > 0
    assert result.quantity % step == 0
    assert result.risk_amount <= capital * risk_pct / 100  # never risks more than intended
    assert result.notional <= capital * share / 100  # never takes more than the share cap
    assert result.risk_amount == result.quantity * (entry - stop)
