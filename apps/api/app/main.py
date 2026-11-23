"""FastAPI application factory.

Run locally from apps/api:
    uv run uvicorn app.main:create_app --factory --reload
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import health
from app.api.errors import register_error_handlers
from app.api.middleware import RequestContextMiddleware
from app.core.config import Settings, get_settings
from app.core.database import check_database, create_engine, create_sessionmaker
from app.core.logging import configure_logging
from app.core.readiness import register_check


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open shared clients at startup and close them at shutdown."""
    settings: Settings = app.state.settings
    engine = create_engine(settings)
    app.state.engine = engine
    app.state.sessionmaker = create_sessionmaker(engine)
    register_check(
        app, "database", partial(check_database, engine, settings.dependency_timeout_seconds)
    )
    try:
        yield
    finally:
        await engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the API. Pass `settings` to override the environment (tests do this)."""
    settings = settings or get_settings()
    configure_logging(settings)

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
    return app
