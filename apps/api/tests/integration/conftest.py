"""Throwaway containers for integration tests, started once per test session."""

from collections.abc import Iterator

import pytest
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

# Same image as infra/docker-compose.dev.yml, so tests match local dev.
POSTGRES_IMAGE = "timescale/timescaledb:2.32.1-pg17"
REDIS_IMAGE = "redis:7-alpine"


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    with PostgresContainer(
        POSTGRES_IMAGE, username="test", password="test", dbname="trading", driver="asyncpg"
    ) as container:
        yield container.get_connection_url()


@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    with RedisContainer(REDIS_IMAGE) as container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(6379)
        yield f"redis://{host}:{port}/0"
