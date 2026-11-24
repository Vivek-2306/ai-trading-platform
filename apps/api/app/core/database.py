"""Async database access (SQLAlchemy 2 + asyncpg).

The engine is created when the app starts and disposed when it stops (see app.main). Routes
get a session through the `SessionDep` dependency; one session per request, committed or
rolled back by the route's own logic.
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.database_url,
        pool_size=settings.database_pool_size,
        pool_pre_ping=True,  # drop dead connections instead of failing a request
        connect_args={"timeout": settings.dependency_timeout_seconds},
    )


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False: objects stay usable after commit (common in async code).
    return async_sessionmaker(engine, expire_on_commit=False)


async def check_database(engine: AsyncEngine, timeout_seconds: float) -> bool:
    """True if the database answers a trivial query within `timeout_seconds`."""
    try:
        async with asyncio.timeout(timeout_seconds), engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    sessionmaker = cast(async_sessionmaker[AsyncSession], request.app.state.sessionmaker)
    async with sessionmaker() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
