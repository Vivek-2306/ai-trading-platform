"""Tests for /health, /version and the OpenAPI document."""

from fastapi.testclient import TestClient

from app import __version__


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version_reports_version_sha_and_environment(client: TestClient) -> None:
    response = client.get("/version")

    assert response.status_code == 200
    assert response.json() == {
        "name": "trading-api",
        "version": __version__,
        "git_sha": "abc1234",
        "environment": "test",
    }


def test_openapi_lists_system_endpoints(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/health" in paths
    assert "/version" in paths


def test_docs_page_is_served(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
