"""Tests for the Redis helpers that don't need a running Redis."""

from app.core.config import Settings
from app.core.redis import check_redis, create_redis


def test_client_uses_configured_url_and_timeouts() -> None:
    client = create_redis(
        Settings(
            _env_file=None, redis_url="redis://cache.example:6380/3", dependency_timeout_seconds=1.5
        )
    )

    kwargs = client.connection_pool.connection_kwargs
    assert kwargs["host"] == "cache.example"
    assert kwargs["port"] == 6380
    assert kwargs["db"] == 3
    assert kwargs["socket_connect_timeout"] == 1.5


async def test_check_redis_false_when_unreachable() -> None:
    client = create_redis(Settings(_env_file=None, redis_url="redis://127.0.0.1:1/0"))
    try:
        assert await check_redis(client, timeout_seconds=1) is False
    finally:
        await client.aclose()
