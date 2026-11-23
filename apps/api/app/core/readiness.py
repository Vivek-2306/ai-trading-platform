"""Readiness checks: one async callable per dependency, run together with a timeout."""

import asyncio
from collections.abc import Awaitable, Callable

from fastapi import FastAPI

ReadinessCheck = Callable[[], Awaitable[bool]]


def register_check(app: FastAPI, name: str, check: ReadinessCheck) -> None:
    checks: dict[str, ReadinessCheck] = app.state.readiness_checks
    checks[name] = check


async def run_readiness_checks(app: FastAPI) -> dict[str, bool]:
    checks: dict[str, ReadinessCheck] = app.state.readiness_checks
    names = list(checks)
    results = await asyncio.gather(*(checks[name]() for name in names), return_exceptions=True)
    return {name: result is True for name, result in zip(names, results, strict=True)}
