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


def test_a_before_time_without_a_zone_is_accepted_as_utc(client: TestClient) -> None:
    # Validation passes (the request then needs a database, which unit tests do not have).
    response = client.get(
        "/data/candles",
        params={"instrument_id": 1, "timeframe": "1h", "before": "2026-11-24T10:00:00"},
    )

    assert response.status_code != 422
