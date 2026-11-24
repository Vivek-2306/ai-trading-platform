"""End-to-end checks of migrations, readiness, DB sessions and Redis against real services."""

import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings
from app.core.database import SessionDep
from app.core.redis import RedisDep
from app.main import create_app

pytestmark = pytest.mark.integration

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def _settings(database_url: str, redis_url: str) -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        database_url=database_url,
        redis_url=redis_url,
        dependency_timeout_seconds=3,
    )


def _installed_extensions(database_url: str) -> set[str]:
    async def query() -> set[str]:
        engine = create_async_engine(database_url)
        try:
            async with engine.connect() as connection:
                rows = await connection.execute(
                    text(
                        "SELECT extname FROM pg_extension "
                        "WHERE extname IN ('timescaledb', 'vector')"
                    )
                )
                return {row[0] for row in rows}
        finally:
            await engine.dispose()

    return asyncio.run(query())


def test_migrations_upgrade_downgrade_and_upgrade_again(postgres_url: str) -> None:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", postgres_url)

    command.upgrade(config, "head")
    assert _installed_extensions(postgres_url) == {"timescaledb", "vector"}

    command.downgrade(config, "base")
    assert _installed_extensions(postgres_url) == set()

    command.upgrade(config, "head")
    assert _installed_extensions(postgres_url) == {"timescaledb", "vector"}


def test_ready_when_database_and_redis_are_up(postgres_url: str, redis_url: str) -> None:
    with TestClient(create_app(_settings(postgres_url, redis_url))) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": "ok", "redis": "ok"}}


def test_not_ready_when_only_database_is_down(redis_url: str) -> None:
    unreachable_db = "postgresql+asyncpg://u:p@127.0.0.1:1/none"
    with TestClient(create_app(_settings(unreachable_db, redis_url))) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["checks"] == {"database": "unavailable", "redis": "ok"}


@pytest.fixture
def app_with_probe_routes(postgres_url: str, redis_url: str) -> FastAPI:
    app = create_app(_settings(postgres_url, redis_url))

    @app.get("/probe/db")
    async def probe_db(session: SessionDep) -> dict[str, int]:
        value = (await session.execute(text("SELECT 41 + 1"))).scalar_one()
        return {"value": value}

    @app.get("/probe/redis")
    async def probe_redis(redis: RedisDep) -> dict[str, object]:
        await redis.set("probe:key", "hello", ex=10)
        return {"value": await redis.get("probe:key")}

    return app


def test_session_dependency_queries_the_database(app_with_probe_routes: FastAPI) -> None:
    with TestClient(app_with_probe_routes) as client:
        assert client.get("/probe/db").json() == {"value": 42}


def test_redis_dependency_round_trips_a_value(app_with_probe_routes: FastAPI) -> None:
    with TestClient(app_with_probe_routes) as client:
        assert client.get("/probe/redis").json() == {"value": "hello"}
