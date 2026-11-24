"""Request validation for the candle endpoints (database queries are covered in integration)."""

from fastapi.testclient import TestClient


def test_candles_needs_instrument_and_timeframe(client: TestClient) -> None:
    response = client.get("/data/candles")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_unknown_timeframe_is_rejected(client: TestClient) -> None:
    response = client.get("/data/candles", params={"instrument_id": 1, "timeframe": "7m"})

    assert response.status_code == 422


def test_limit_is_bounded(client: TestClient) -> None:
    for bad in (0, 1001):
        response = client.get(
            "/data/candles", params={"instrument_id": 1, "timeframe": "1h", "limit": bad}
        )
        assert response.status_code == 422


def test_instrument_id_must_be_positive(client: TestClient) -> None:
    response = client.get("/data/candles", params={"instrument_id": 0, "timeframe": "1h"})

    assert response.status_code == 422


def test_signals_filters_are_validated(client: TestClient) -> None:
    for params in (
        {"timeframe": "7m"},
        {"action": "MAYBE"},
        {"limit": 0},
        {"limit": 201},
        {"instrument_id": 0},
        {"before_id": 0},
    ):
        assert client.get("/signals", params=params).status_code == 422, params


def test_kill_switch_request_is_validated(client: TestClient) -> None:
    assert client.post("/risk/kill-switch", json={"active": True}).status_code == 422
    short = client.post("/risk/kill-switch", json={"active": True, "reason": "x"})
    assert short.status_code == 422


def test_signal_risk_record_is_mapped_for_a_fresh_actionable_buy() -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    from app.api.signals import _out
    from app.data.models import Instrument, Signal

    now = datetime(2026, 11, 24, 9, 30, tzinfo=UTC)
    instrument = Instrument(id=1, venue="binance", symbol="BTC/USDT", asset_class="crypto")

    def signal(action: str, risk: dict) -> Signal:  # type: ignore[type-arg]
        return Signal(
            id=1,
            instrument_id=1,
            timeframe="1h",
            candle_ts=datetime(2026, 11, 24, 8, 0, tzinfo=UTC),
            action=action,
            confidence=Decimal("0.7"),
            reasons=[],
            inputs={},
            rule_version="rules-v1",
            risk=risk,
            created_at=now,
        )

    plan = {
        "entry": "100",
        "stop": "97",
        "target": "106",
        "risk_per_unit": "3",
        "reward_per_unit": "6",
        "risk_reward": "2.00",
    }
    size = {
        "quantity": "1.5",
        "notional": "150",
        "risk_amount": "4.5",
        "capital_share_pct": "15",
        "limited_by": "risk",
    }
    buy = _out(signal("BUY", {"assessed": True, "plan": plan, "size": size}), instrument, now)
    legacy = _out(signal("SELL", {}), instrument, now)
    vetoed = _out(
        signal(
            "NO_TRADE",
            {
                "assessed": True,
                "rules_action": "BUY",
                "plan": plan,
                "size": size,
                "vetoes": [{"code": "max_open_positions", "text": "3 open"}],
            },
        ),
        instrument,
        now,
    )

    assert buy.actionable and buy.risk.plan and buy.risk.plan.stop == Decimal("97")
    assert not legacy.actionable and not legacy.risk.assessed  # older than the risk engine
    assert not vetoed.actionable and vetoed.risk.plan is None  # no plan for a refused BUY
    assert not vetoed.risk.portfolio_tracked
    assert vetoed.risk.rules_action == "BUY" and vetoed.risk.vetoes[0].code == "max_open_positions"
