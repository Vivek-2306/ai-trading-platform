"""The veto layer: every refusal, and what always holds."""

import json
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.data.models import SignalAction
from app.risk.limits import RiskLimits
from app.risk.plan import TradePlan
from app.risk.sizing import PositionSize
from app.risk.veto import PortfolioState, RiskAssessment, assess
from app.signals.rules import Decision, Reason

D = Decimal
DEFAULT_ENTRY = D("100")


def limits(**over: object) -> RiskLimits:
    return RiskLimits(_env_file=None, **over)  # type: ignore[arg-type]


def decision(action: SignalAction = SignalAction.BUY) -> Decision:
    return Decision(
        action,
        D("0.7"),
        [Reason("trend_up", "Uptrend.", "buy", 2.0)],
        {"close": 100.0, "atr": 2.0},
    )


def run(
    action: SignalAction = SignalAction.BUY,
    *,
    entry: Decimal | None = DEFAULT_ENTRY,
    atr: float | None = 2.0,
    lim: RiskLimits | None = None,
    state: PortfolioState | None = None,
    kill: bool = False,
    symbol: str = "BTC/USDT",
) -> RiskAssessment:
    return assess(
        decision(action),
        symbol=symbol,
        entry=entry,
        atr=atr,
        limits=lim or limits(),
        state=state or PortfolioState(),
        kill_switch_on=kill,
    )


def codes(a: RiskAssessment) -> set[str]:
    return {v.code for v in a.vetoes}


def test_a_good_buy_passes_with_a_plan_and_a_size() -> None:
    a = run()

    assert a.action is SignalAction.BUY and a.actionable
    assert isinstance(a.plan, TradePlan) and isinstance(a.size, PositionSize)
    assert a.plan.stop == D("97") and a.plan.target == D("106")
    # 0.5% of 1000 = 5 at risk; 3 per unit -> 1.66666 BTC-ish rounded down to the lot size.
    assert a.size.quantity == D("1.66666")
    assert a.size.risk_amount <= D("5")
    assert a.vetoes == []


def test_a_buy_at_the_open_position_limit_is_vetoed() -> None:
    a = run(lim=limits(max_open_positions=2), state=PortfolioState(open_positions=2))

    assert a.action is SignalAction.NO_TRADE and not a.actionable
    assert codes(a) == {"max_open_positions"}
    assert a.rules_action is SignalAction.BUY  # the record keeps what the rules said


def test_a_buy_after_the_daily_loss_limit_is_vetoed() -> None:
    a = run(lim=limits(capital="1000", max_daily_loss_pct="2"), state=PortfolioState(0, D("20")))

    assert a.action is SignalAction.NO_TRADE and codes(a) == {"daily_loss_limit"}


def test_every_failing_limit_is_reported_together() -> None:
    a = run(
        lim=limits(max_open_positions=1),
        state=PortfolioState(open_positions=1, realized_loss_today=D("999")),
    )

    assert codes(a) == {"max_open_positions", "daily_loss_limit"}


@pytest.mark.parametrize(
    "kwargs, code",
    [
        ({"atr": 30.0}, "stop_too_wide"),  # stop 45% below the entry
        ({"atr": None}, "bad_atr"),
        ({"atr": 0.0}, "bad_atr"),
        ({"entry": None}, "bad_entry"),
        ({"entry": D("1"), "atr": 4.0}, "stop_below_zero"),
    ],
)
def test_a_bad_plan_vetoes_the_buy(kwargs: dict[str, object], code: str) -> None:
    a = run(**kwargs)  # type: ignore[arg-type]

    assert a.action is SignalAction.NO_TRADE and codes(a) == {code}
    assert a.plan is None and a.size is None


def test_a_size_that_rounds_to_nothing_vetoes_the_buy() -> None:
    a = run(lim=limits(capital="1"), entry=D("50000"), atr=1000.0)

    assert a.action is SignalAction.NO_TRADE and codes(a) == {"size_too_small"}


def test_the_kill_switch_stops_everything() -> None:
    for action in SignalAction:
        a = run(action, kill=True)
        assert a.action is SignalAction.NO_TRADE, action
        assert codes(a) == {"kill_switch"} and not a.actionable and a.plan is None


def test_sell_hold_and_no_trade_pass_through_unchanged() -> None:
    for action in (SignalAction.SELL, SignalAction.HOLD, SignalAction.NO_TRADE):
        a = run(action)
        assert a.action is action and a.vetoes == [] and a.plan is None


def test_the_record_is_json_with_exact_decimal_strings() -> None:
    record = run().as_record()

    assert json.loads(json.dumps(record)) == record
    assert record["assessed"] is True and record["rules_action"] == "BUY"
    assert record["plan"]["stop"] == "97.00000000" or record["plan"]["stop"] == "97"
    assert record["size"]["limited_by"] == "risk"
    assert "admin_token" not in record["limits"]
    assert record["limits"]["risk_per_trade_pct"] == "0.5"


def test_an_assessment_cannot_be_forged() -> None:
    with pytest.raises(TypeError, match="only be created by assess"):
        RiskAssessment(
            rules_action=SignalAction.BUY,
            action=SignalAction.BUY,
            plan=None,
            size=None,
            vetoes=[],
            kill_switch=False,
            limits={},
        )


@given(
    action=st.sampled_from(list(SignalAction)),
    entry=st.one_of(st.none(), st.decimals(min_value=D("0"), max_value=D("500000"), places=4)),
    atr=st.one_of(
        st.none(),
        st.just(float("nan")),
        st.just(float("inf")),
        st.floats(min_value=-5, max_value=1e5, allow_nan=False, allow_infinity=False),
    ),
    open_positions=st.integers(0, 30),
    loss=st.decimals(min_value=D("0"), max_value=D("5000"), places=2),
    kill=st.booleans(),
)
def test_a_buy_only_survives_with_a_plan_a_size_and_every_limit_respected(
    action: SignalAction,
    entry: Decimal | None,
    atr: float | None,
    open_positions: int,
    loss: Decimal,
    kill: bool,
) -> None:
    lim = limits()
    a = assess(
        decision(action),
        symbol="ETH/USDT",
        entry=entry,
        atr=atr,
        limits=lim,
        state=PortfolioState(open_positions, loss),
        kill_switch_on=kill,
    )

    if kill:
        assert a.action is SignalAction.NO_TRADE and not a.actionable
    if a.action is SignalAction.BUY:
        assert not kill and a.rules_action is SignalAction.BUY
        assert a.plan is not None and a.size is not None and a.vetoes == []
        assert open_positions < lim.max_open_positions
        assert loss < lim.capital * lim.max_daily_loss_pct / 100
        assert a.size.risk_amount <= lim.capital * lim.risk_per_trade_pct / 100
        assert a.size.notional <= lim.capital * lim.max_capital_share_pct / 100
        assert a.plan.risk_reward >= lim.min_risk_reward
    if a.rules_action is SignalAction.BUY and a.action is not SignalAction.BUY:
        assert a.vetoes, "a refused BUY must say why"
