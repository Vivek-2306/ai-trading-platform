"""Application settings, loaded from environment variables (and the repo-root env file in dev)."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _find_repo_root(start: Path) -> Path | None:
    """The monorepo root (has pnpm-workspace.yaml), or None when running outside it (Docker)."""
    for folder in start.parents:
        if (folder / "pnpm-workspace.yaml").is_file():
            return folder
    return None


REPO_ROOT = _find_repo_root(Path(__file__).resolve())
# In the repo, load the root env file for local dev; in a container, env vars only.
ENV_FILE = REPO_ROOT / ".env" if REPO_ROOT else None


class Settings(BaseSettings):
    """Typed settings. Every field maps to an upper-case environment variable."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "trading-api"
    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["debug", "info", "warning", "error"] = "info"
    # Optional rotating JSON log file (e.g. logs/api.log). Off by default.
    log_file: str | None = None
    # Optional error reporting. Off unless set; no personal data is sent.
    sentry_dsn: str | None = None
    trading_mode: Literal["paper", "live"] = "paper"

    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # Set by CI / the Docker build so /version can report exactly what is running.
    git_sha: str | None = None

    # Dev default matches infra/docker-compose.dev.yml; production always sets DATABASE_URL.
    database_url: str = "postgresql+asyncpg://trading:trading_dev@localhost:5432/trading"
    database_pool_size: int = Field(default=5, ge=1, le=50)
    # Cache, live prices and pub/sub (the Celery broker uses CELERY_BROKER_URL).
    redis_url: str = "redis://localhost:6379/0"

    # Background jobs. Separate Redis databases keep queues, results and cache apart.
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    heartbeat_interval_seconds: float = Field(default=60, ge=5)
    # Longer than the longest background task (6 h default); see celery_app.py.
    task_visibility_timeout_seconds: int = Field(default=6 * 3600, ge=60)
    # Seconds a readiness check may wait for a dependency before calling it unavailable.
    dependency_timeout_seconds: float = Field(default=2.0, gt=0, le=30)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept a comma-separated string (as in the env file) or a list."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("cors_origins")
    @classmethod
    def _reject_wildcard_origin(cls, origins: list[str]) -> list[str]:
        """The API allows credentials, so a wildcard would let any site call it as the user."""
        if "*" in origins:
            raise ValueError("CORS_ORIGINS must list exact origins; '*' is not allowed")
        return origins

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Settings for the running process, read once."""
    return Settings()
