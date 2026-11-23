"""Tests for /health/ready and the readiness check runner (no Docker needed)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.readiness import register_check, run_readiness_checks
from app.main import create_app


def _unreachable_settings() -> Settings:
    # Port 1 on localhost refuses connections immediately: a "down" database.
    return Settings(
        _env_file=None,
        app_env="test",
        database_url="postgresql+asyncpg://user:pw@127.0.0.1:1/none",
        dependency_timeout_seconds=1,
    )


def test_ready_returns_503_when_database_is_down() -> None:
    with TestClient(create_app(_unreachable_settings())) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "checks": {"database": "unavailable"}}


def test_ready_does_not_leak_connection_details() -> None:
    with TestClient(create_app(_unreachable_settings())) as client:
        response = client.get("/health/ready")

    assert "127.0.0.1" not in response.text
    assert "pw" not in response.text


def test_liveness_stays_ok_when_database_is_down() -> None:
    with TestClient(create_app(_unreachable_settings())) as client:
        assert client.get("/health").status_code == 200


async def test_run_checks_reports_each_dependency() -> None:
    app = FastAPI()
    app.state.readiness_checks = {}

    async def ok() -> bool:
        return True

    async def down() -> bool:
        return False

    async def broken() -> bool:
        raise RuntimeError("boom")

    register_check(app, "a", ok)
    register_check(app, "b", down)
    register_check(app, "c", broken)

    assert await run_readiness_checks(app) == {"a": True, "b": False, "c": False}
