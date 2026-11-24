"""The kill switch: one switch that stops every new signal from being actionable.

State lives in the database (an append-only log, newest row wins), so it survives restarts and
every change is on record with who, when and why.

Command line (from apps/api):
    uv run python -m app.risk.killswitch status
    uv run python -m app.risk.killswitch on  --reason "exchange outage"
    uv run python -m app.risk.killswitch off --reason "checked, all clear"
"""

import argparse
import asyncio
import getpass
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.logging import get_logger
from app.data.models import KillSwitchEvent

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class KillSwitchState:
    active: bool
    since: datetime | None = None
    actor: str | None = None
    reason: str | None = None


async def kill_switch_state(session: AsyncSession) -> KillSwitchState:
    """The current state: off if nothing has ever been recorded."""
    newest = (
        await session.execute(select(KillSwitchEvent).order_by(KillSwitchEvent.id.desc()).limit(1))
    ).scalar_one_or_none()
    if newest is None:
        return KillSwitchState(active=False)
    return KillSwitchState(newest.active, newest.created_at, newest.actor, newest.reason)


async def set_kill_switch(
    session: AsyncSession, *, active: bool, actor: str, reason: str
) -> tuple[KillSwitchState, bool]:
    """Switch on or off. Returns the new state and whether anything changed. Switching to the
    state it is already in records nothing (the log stays a list of real changes)."""
    reason = reason.strip()
    if len(reason) < 3:
        raise ValueError("a reason (at least 3 characters) is required")
    current = await kill_switch_state(session)
    if current.active == active:
        return current, False
    session.add(KillSwitchEvent(active=active, actor=actor[:64], reason=reason[:500]))
    await session.commit()
    logger.warning("kill_switch_changed", active=active, actor=actor, reason=reason[:500])
    return await kill_switch_state(session), True


async def recent_events(session: AsyncSession, limit: int = 10) -> list[KillSwitchEvent]:
    rows = await session.execute(
        select(KillSwitchEvent).order_by(KillSwitchEvent.id.desc()).limit(limit)
    )
    return list(rows.scalars())


async def _cli(args: argparse.Namespace) -> int:
    engine = create_async_engine(get_settings().database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            if args.command == "status":
                state = await kill_switch_state(session)
                print(f"kill switch: {'ON' if state.active else 'off'}")  # noqa: T201
                if state.since:
                    print(f"  since {state.since.isoformat()} by {state.actor}: {state.reason}")  # noqa: T201
                return 0
            state, changed = await set_kill_switch(
                session,
                active=args.command == "on",
                actor=f"cli:{getpass.getuser()}",
                reason=args.reason,
            )
            verb = "changed to" if changed else "already"
            print(f"kill switch {verb} {'ON' if state.active else 'off'}")  # noqa: T201
            return 0
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Show or change the kill switch.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    for name in ("on", "off"):
        command = sub.add_parser(name)
        command.add_argument("--reason", required=True, help="why (kept in the audit log)")
    raise SystemExit(asyncio.run(_cli(parser.parse_args())))


if __name__ == "__main__":
    main()
