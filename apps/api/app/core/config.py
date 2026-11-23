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
    trading_mode: Literal["paper", "live"] = "paper"

    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # Set by CI / the Docker build so /version can report exactly what is running.
    git_sha: str | None = None

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
