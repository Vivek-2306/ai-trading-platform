"""Async Redis client: created at startup, closed at shutdown (see app.main)."""

import asyncio
from typing import Annotated, cast

from fastapi import Depends, Request
from redis.asyncio import Redis

from app.core.config import Settings


def create_redis(settings: Settings) -> Redis:
    return Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=settings.dependency_timeout_seconds,
        socket_timeout=settings.dependency_timeout_seconds,
        health_check_interval=30,
    )


async def check_redis(client: Redis, timeout_seconds: float) -> bool:
    """True if Redis answers PING within `timeout_seconds`."""
    try:
        async with asyncio.timeout(timeout_seconds):
            return bool(await client.ping())
    except Exception:
        return False


def get_redis(request: Request) -> Redis:
    return cast(Redis, request.app.state.redis)


RedisDep = Annotated[Redis, Depends(get_redis)]
