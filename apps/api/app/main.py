"""FastAPI application factory.

Run locally from apps/api:
    uv run uvicorn app.main:create_app --factory --reload
"""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from functools import partial

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import data, health, risk, signals, stream
from app.api.errors import register_error_handlers
from app.api.middleware import RequestContextMiddleware
from app.core.config import Settings, get_settings
from app.core.database import check_database, create_engine, create_sessionmaker
from app.core.error_reporting import init_error_reporting
from app.core.logging import configure_logging
from app.core.readiness import register_check
from app.core.redis import check_redis, create_redis
from app.risk.limits import get_risk_limits


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open shared clients at startup and close them at shutdown.

    Each client is registered for cleanup as soon as it exists, so a failure part-way
    through startup still closes whatever was already opened.
    """
    settings: Settings = app.state.settings
    timeout = settings.dependency_timeout_seconds
    async with AsyncExitStack() as cleanup:
        engine = create_engine(settings)
        cleanup.push_async_callback(engine.dispose)
        app.state.engine = engine
        app.state.sessionmaker = create_sessionmaker(engine)
        register_check(app, "database", partial(check_database, engine, timeout))

        redis = create_redis(settings)
        cleanup.push_async_callback(redis.aclose)
        app.state.redis = redis
        register_check(app, "redis", partial(check_redis, redis, timeout))

        yield


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the API. Pass `settings` to override the environment (tests do this)."""
    settings = settings or get_settings()
    configure_logging(settings)
    init_error_reporting(settings)
    get_risk_limits()  # fail at startup, not at the first signal, if a limit is unsafe

    app = FastAPI(
        title="AI Trading Platform API",
        version=__version__,
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.readiness_checks = {}

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    # Added last so it runs first: every request gets an ID before anything else.
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)

    app.include_router(health.router)
    app.include_router(data.router)
    app.include_router(stream.router)
    app.include_router(signals.router)
    app.include_router(risk.router)
    return app
