"""Liveness and version endpoints."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app import __version__
from app.api.deps import SettingsDep

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: Literal["ok"]


class VersionResponse(BaseModel):
    name: str
    version: str
    git_sha: str | None
    environment: str


@router.get("/health", summary="Liveness check")
async def health() -> HealthResponse:
    """Returns ok while the process is up. Dependency checks live in /health/ready (later)."""
    return HealthResponse(status="ok")


@router.get("/version", summary="Running version")
async def version(settings: SettingsDep) -> VersionResponse:
    return VersionResponse(
        name=settings.app_name,
        version=__version__,
        git_sha=settings.git_sha,
        environment=settings.app_env,
    )
