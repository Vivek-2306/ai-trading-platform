"""Liveness, readiness and version endpoints."""

from typing import Literal

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel

from app import __version__
from app.api.deps import SettingsDep
from app.core.readiness import run_readiness_checks

router = APIRouter(tags=["system"])

CheckStatus = Literal["ok", "unavailable"]


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, CheckStatus]


class VersionResponse(BaseModel):
    name: str
    version: str
    git_sha: str | None
    environment: str


@router.get("/health", summary="Liveness check")
async def health() -> HealthResponse:
    """Returns ok while the process is up. It does not check dependencies; see /health/ready."""
    return HealthResponse(status="ok")


@router.get(
    "/health/ready",
    summary="Readiness check",
    responses={503: {"model": ReadinessResponse, "description": "A dependency is down"}},
)
async def ready(request: Request, response: Response) -> ReadinessResponse:
    """Checks every dependency (database, and Redis once added). 503 if any is down."""
    results = await run_readiness_checks(request.app)
    checks: dict[str, CheckStatus] = {
        name: "ok" if healthy else "unavailable" for name, healthy in results.items()
    }
    if all(results.values()):
        return ReadinessResponse(status="ready", checks=checks)
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status="not_ready", checks=checks)


@router.get("/version", summary="Running version")
async def version(settings: SettingsDep) -> VersionResponse:
    return VersionResponse(
        name=settings.app_name,
        version=__version__,
        git_sha=settings.git_sha,
        environment=settings.app_env,
    )
