"""Liveness of the stream service, shared through Redis.

The service refreshes a heartbeat key on every message it receives. The container health
check reads it: no recent heartbeat means the stream is stuck or disconnected.
Run `python -m app.stream.health` (exit 0 = healthy).
"""

import asyncio
import sys
from datetime import UTC, datetime

from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.redis import create_redis

HEARTBEAT_KEY = "stream:heartbeat"
MAX_AGE_SECONDS = 90


async def beat(redis: Redis, now: datetime | None = None) -> None:
    stamp = (now or datetime.now(UTC)).isoformat()
    await redis.set(HEARTBEAT_KEY, stamp, ex=MAX_AGE_SECONDS * 2)


def is_fresh(value: str | None, now: datetime, max_age: float = MAX_AGE_SECONDS) -> bool:
    if not value:
        return False
    try:
        last = datetime.fromisoformat(value)
    except ValueError:
        return False
    return 0 <= (now - last).total_seconds() <= max_age


async def _check() -> bool:
    redis = create_redis(get_settings())
    try:
        value = await redis.get(HEARTBEAT_KEY)
        text = value.decode() if isinstance(value, bytes) else value
        return is_fresh(text, datetime.now(UTC))
    except Exception:
        return False
    finally:
        await redis.aclose()


def main() -> None:
    sys.exit(0 if asyncio.run(_check()) else 1)


if __name__ == "__main__":
    main()
