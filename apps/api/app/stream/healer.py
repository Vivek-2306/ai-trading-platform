"""Repair missed candles. The stream can miss minutes (disconnects, restarts), so a REST
backfill runs at startup, after every reconnect, and every few minutes as a safety net.
"""

import asyncio
import contextlib
from collections.abc import Awaitable, Callable

from app.core.logging import get_logger

logger = get_logger(__name__)


class GapHealer:
    def __init__(self, heal: Callable[[], Awaitable[None]], interval_seconds: float = 300) -> None:
        self._heal = heal
        self._interval = interval_seconds
        self._wake = asyncio.Event()

    def request(self) -> None:
        """Ask for a gap check soon (called after a reconnect)."""
        self._wake.set()

    async def run(self) -> None:
        """Heal now, then again on every request and every interval. Runs until cancelled."""
        while True:
            self._wake.clear()
            try:
                await self._heal()
            except Exception:
                # A failed repair must not stop the next one.
                logger.exception("stream_gap_heal_failed")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._wake.wait(), timeout=self._interval)
