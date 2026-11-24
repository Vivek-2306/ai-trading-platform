"""Shared FastAPI dependencies."""

from typing import Annotated, cast

from fastapi import Depends, Request

from app.core.config import Settings


def get_app_settings(request: Request) -> Settings:
    """The settings the app was created with (lets tests inject their own)."""
    return cast(Settings, request.app.state.settings)


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
