"""Risk limits: safe defaults, env overrides, and refusal of unsafe values."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.risk.limits import RiskLimits, get_risk_limits

D = Decimal


def make(**over: object) -> RiskLimits:
    return RiskLimits(_env_file=None, **over)  # type: ignore[arg-type]


def test_defaults_are_conservative() -> None:
    limits = make()

    assert limits.risk_per_trade_pct == D("0.5")
    assert limits.max_capital_share_pct == D("20")
    assert limits.max_daily_loss_pct == D("2")
    assert limits.max_open_positions == 3
    assert limits.min_risk_reward == D("1.5")
    assert limits.target_atr_multiple / limits.stop_atr_multiple >= limits.min_risk_reward
    assert limits.admin_token is None


def test_values_come_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RISK_CAPITAL", "25000.50")
    monkeypatch.setenv("RISK_RISK_PER_TRADE_PCT", "1")
    monkeypatch.setenv("RISK_MAX_OPEN_POSITIONS", "5")
    monkeypatch.setenv("RISK_ADMIN_TOKEN", "")

    limits = make()

    assert limits.capital == D("25000.50")  # an exact decimal, not a float
    assert limits.risk_per_trade_pct == D("1")
    assert limits.max_open_positions == 5
    assert limits.admin_token is None  # empty means unset


@pytest.mark.parametrize(
    "over",
    [
        {"risk_per_trade_pct": "5"},  # above the 2% ceiling
        {"risk_per_trade_pct": "0"},
        {"risk_per_trade_pct": "-1"},
        {"max_capital_share_pct": "150"},
        {"max_daily_loss_pct": "50"},
        {"max_open_positions": 0},
        {"max_open_positions": 100},
        {"min_risk_reward": "0.5"},
        {"stop_atr_multiple": "0.1"},
        {"capital": "0"},
        {"capital": "-5"},
        {"capital": "NaN"},
        {"capital": "Infinity"},
        {"max_stop_distance_pct": "80"},
    ],
)
def test_unsafe_values_are_rejected(over: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        make(**over)


def test_a_target_that_can_never_meet_the_minimum_is_rejected() -> None:
    with pytest.raises(ValidationError, match="every trade would be vetoed"):
        make(stop_atr_multiple="2", target_atr_multiple="2", min_risk_reward="1.5")


def test_risk_per_trade_cannot_exceed_the_daily_loss_limit() -> None:
    with pytest.raises(ValidationError, match="must not exceed"):
        make(risk_per_trade_pct="2", max_daily_loss_pct="1")


def test_the_admin_token_never_shows_in_a_repr() -> None:
    limits = make(admin_token="s3cret-token-0123456")

    assert "s3cret-token-0123456" not in repr(limits)
    assert (
        limits.admin_token is not None
        and limits.admin_token.get_secret_value() == "s3cret-token-0123456"
    )


def test_the_app_refuses_to_start_with_an_unsafe_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import Settings
    from app.main import create_app

    monkeypatch.setenv("RISK_RISK_PER_TRADE_PCT", "50")
    get_risk_limits.cache_clear()
    try:
        with pytest.raises(ValidationError):
            create_app(Settings(_env_file=None, app_env="test"))
    finally:
        monkeypatch.delenv("RISK_RISK_PER_TRADE_PCT")
        get_risk_limits.cache_clear()


@pytest.mark.parametrize("token", [" ", "a", "short-token", "                "])
def test_a_weak_admin_token_is_rejected(token: str) -> None:
    with pytest.raises(ValidationError, match="at least 16 characters"):
        make(admin_token=token)


def test_limits_cannot_be_changed_after_validation() -> None:
    limits = make()

    with pytest.raises(ValidationError):
        limits.risk_per_trade_pct = D("50")  # type: ignore[misc]
