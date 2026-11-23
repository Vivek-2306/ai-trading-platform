"""Tests for request IDs, request logging and the error format."""

from collections.abc import Iterator

import pytest
import structlog
from fastapi import FastAPI
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from app.api.middleware import resolve_request_id
from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def app_with_test_routes(settings: Settings) -> FastAPI:
    app = create_app(settings)

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("secret internal detail")

    @app.get("/items/{item_id}")
    async def item(item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    return app


@pytest.fixture
def error_client(app_with_test_routes: FastAPI) -> Iterator[TestClient]:
    with TestClient(app_with_test_routes, raise_server_exceptions=False) as test_client:
        yield test_client


def test_generates_request_id_when_missing(client: TestClient) -> None:
    response = client.get("/health")

    request_id = response.headers["X-Request-ID"]
    assert len(request_id) == 32


def test_reuses_valid_incoming_request_id(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "abc-123"})

    assert response.headers["X-Request-ID"] == "abc-123"


@pytest.mark.parametrize("bad", ["", "has spaces", "x" * 129, "line\nbreak", "<script>"])
def test_replaces_invalid_incoming_request_id(bad: str) -> None:
    assert resolve_request_id(bad) != bad


def test_request_is_logged_with_its_id(client: TestClient) -> None:
    with capture_logs() as logs:
        response = client.get("/health", headers={"X-Request-ID": "log-me"})

    entry = next(log for log in logs if log["event"] == "request")
    assert entry["status"] == 200
    assert entry["log_level"] == "info"
    assert isinstance(entry["duration_ms"], float)
    assert response.headers["X-Request-ID"] == "log-me"


def test_unhandled_error_returns_generic_json_without_details(
    error_client: TestClient,
) -> None:
    with capture_logs() as logs:
        response = error_client.get("/boom", headers={"X-Request-ID": "err-1"})

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "err-1"
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "Internal server error",
            "request_id": "err-1",
        }
    }
    assert "secret internal detail" not in response.text
    assert any(log["event"] == "unhandled_error" for log in logs)


def test_not_found_uses_error_format(client: TestClient) -> None:
    response = client.get("/does-not-exist")

    assert response.status_code == 404
    body = response.json()["error"]
    assert body["code"] == "http_404"
    assert body["request_id"] == response.headers["X-Request-ID"]


def test_validation_error_uses_error_format(error_client: TestClient) -> None:
    response = error_client.get("/items/not-a-number")

    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "validation_error"
    assert body["details"][0]["loc"] == ["path", "item_id"]


def test_method_not_allowed_keeps_allow_header(client: TestClient) -> None:
    response = client.post("/health")

    assert response.status_code == 405
    assert response.headers["Allow"] == "GET"
    assert response.json()["error"]["code"] == "http_405"


def test_validation_details_do_not_echo_input(error_client: TestClient) -> None:
    response = error_client.get("/items/secret-value")

    detail = response.json()["error"]["details"][0]
    assert set(detail) == {"loc", "msg", "type"}
    assert "secret-value" not in response.text


def test_failed_request_is_still_logged_with_status_500(error_client: TestClient) -> None:
    with capture_logs() as logs:
        error_client.get("/boom")

    entry = next(log for log in logs if log["event"] == "request")
    assert entry["status"] == 500


def test_request_context_is_cleared_after_request(client: TestClient) -> None:
    client.get("/health", headers={"X-Request-ID": "leaky"})

    assert structlog.contextvars.get_contextvars() == {}
