"""Risk status and the kill switch.

Switching the kill switch ON is always allowed (it only makes the system safer). Switching it
OFF through the API needs the admin token (RISK_ADMIN_TOKEN) in the X-Admin-Token header; with
no token configured it can only be done from the command line. The web app does not forward
these endpoints to the browser: only the server side reads them.
"""

import hmac
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.core.database import SessionDep
from app.risk.killswitch import kill_switch_state, recent_events, set_kill_switch
from app.risk.limits import get_risk_limits

router = APIRouter(prefix="/risk", tags=["risk"])


class KillSwitchOut(BaseModel):
    active: bool
    since: datetime | None = None
    actor: str | None = None
    reason: str | None = None


class KillSwitchEventOut(BaseModel):
    id: int
    active: bool
    actor: str
    reason: str
    created_at: datetime


class LimitsOut(BaseModel):
    capital: Decimal
    risk_per_trade_pct: Decimal
    max_capital_share_pct: Decimal
    max_daily_loss_pct: Decimal
    max_open_positions: int
    min_risk_reward: Decimal
    stop_atr_multiple: Decimal
    target_atr_multiple: Decimal
    max_stop_distance_pct: Decimal


class RiskStatus(BaseModel):
    kill_switch: KillSwitchOut
    limits: LimitsOut
    recent_events: list[KillSwitchEventOut]


class KillSwitchRequest(BaseModel):
    active: bool
    reason: Annotated[str, Field(min_length=3, max_length=200)]


@router.get("/status", summary="Risk limits and kill switch state")
async def status(session: SessionDep) -> RiskStatus:
    """The kill switch state with its recent changes, and the active risk limits."""
    state = await kill_switch_state(session)
    events = await recent_events(session, 10)
    limits = get_risk_limits()
    return RiskStatus(
        kill_switch=KillSwitchOut(
            active=state.active, since=state.since, actor=state.actor, reason=state.reason
        ),
        limits=LimitsOut(**limits.model_dump(exclude={"admin_token"})),
        recent_events=[
            KillSwitchEventOut(
                id=e.id, active=e.active, actor=e.actor, reason=e.reason, created_at=e.created_at
            )
            for e in events
        ],
    )


@router.post(
    "/kill-switch",
    summary="Switch the kill switch on or off",
    responses={
        401: {"description": "Switching off needs the admin token (or use the command line)"},
    },
)
async def change_kill_switch(
    body: KillSwitchRequest,
    session: SessionDep,
    x_admin_token: Annotated[str | None, Header()] = None,
) -> KillSwitchOut:
    """ON needs nothing. OFF needs the admin token."""
    if not body.active:
        token = get_risk_limits().admin_token
        supplied = (x_admin_token or "").encode()
        # The same answer whether no token is configured or the guess is wrong, so a caller
        # learns nothing about the setup. Without a token, use the command line.
        expected = token.get_secret_value().encode() if token else b""
        if token is None or not hmac.compare_digest(supplied, expected):
            raise HTTPException(status_code=401, detail="Not allowed. Use the command line.")
    state, _ = await set_kill_switch(session, active=body.active, actor="api", reason=body.reason)
    return KillSwitchOut(
        active=state.active, since=state.since, actor=state.actor, reason=state.reason
    )
