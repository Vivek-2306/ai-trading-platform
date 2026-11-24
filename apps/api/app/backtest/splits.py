"""Splitting history into a tuning region, walk-forward windows and a locked out-of-sample period.

The rule that keeps backtests honest: data you used to choose settings cannot also be used to
judge them. So the most recent slice of history is LOCKED. Tuning and walk-forward code only
ever receives the tuning candles; the locked candles cannot be read without `unlock()`, which
records which configuration is being judged. Judging a second, different configuration on the
same locked period is refused (that would turn it into tuning data). Judging the same
configuration again is fine, so a result can be reproduced.

The lock is by START TIME, not by fraction, so new data extends the locked period instead of
moving it: the first time a (symbol, timeframe, strategy) is judged, the start of the locked
period is fixed (default: the last 20% of history) and stays there.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.analysis.features import MIN_CANDLES
from app.data.adapters.base import RawCandle


class OosLockedError(Exception):
    """The locked out-of-sample period was already used to judge a different configuration."""


@dataclass(frozen=True, slots=True)
class OosKey:
    symbol: str
    timeframe: str
    strategy: str


@dataclass(frozen=True, slots=True)
class OosClaim:
    oos_start: datetime  # where the locked period starts (fixed at the first claim)
    config_hash: str | None  # the configuration judged on it, once there is one


class OosRegistry(Protocol):
    """Remembers, per key, where the locked period starts and which configuration judged it."""

    def get(self, key: OosKey) -> OosClaim | None: ...

    def set_start(self, key: OosKey, oos_start: datetime) -> None: ...

    def set_judged(self, key: OosKey, config_hash: str) -> None: ...


class MemoryRegistry:
    """For tests and one-off experiments. The database one lives with stored runs."""

    def __init__(self) -> None:
        self._claims: dict[OosKey, OosClaim] = {}

    def get(self, key: OosKey) -> OosClaim | None:
        return self._claims.get(key)

    def set_start(self, key: OosKey, oos_start: datetime) -> None:
        self._claims[key] = OosClaim(oos_start, None)

    def set_judged(self, key: OosKey, config_hash: str) -> None:
        claim = self._claims[key]
        self._claims[key] = OosClaim(claim.oos_start, config_hash)


@dataclass(frozen=True, slots=True)
class Segment:
    """A run of candles: indices start (included) to end (excluded) in the full history."""

    name: str
    start: int
    end: int

    def __len__(self) -> int:
        return self.end - self.start


class LockedOos:
    """The out-of-sample candles. The only way to read them is `unlock`."""

    __slots__ = ("_candles", "_key", "_registry", "oos_start", "segment")

    def __init__(
        self,
        candles: list[RawCandle],
        segment: Segment,
        key: OosKey,
        registry: OosRegistry,
        oos_start: datetime,
    ) -> None:
        self._candles = candles
        self.segment = segment
        self._key = key
        self._registry = registry
        self.oos_start = oos_start

    def __repr__(self) -> str:
        return f"LockedOos({len(self._candles)} candles from {self.oos_start.isoformat()}, locked)"

    def unlock(self, config_hash: str) -> list[RawCandle]:
        """The candles, for judging ONE configuration. Refused if another was already judged."""
        claim = self._registry.get(self._key)
        if claim is not None and claim.config_hash not in (None, config_hash):
            raise OosLockedError(
                f"The out-of-sample period for {self._key.symbol} {self._key.timeframe} "
                f"({self._key.strategy}) from {self.oos_start.isoformat()} was already used to "
                f"judge configuration {claim.config_hash}. Judging {config_hash} on it too would "
                "make it tuning data. Wait for new data (it extends the locked period) or "
                "judge only on the tuning region."
            )
        if claim is None or claim.config_hash is None:
            self._registry.set_judged(self._key, config_hash)
        return list(self._candles)


@dataclass(frozen=True, slots=True)
class Splits:
    tuning: list[RawCandle]  # everything before the locked period
    tuning_segment: Segment
    oos: LockedOos


def make_splits(
    candles: list[RawCandle],
    key: OosKey,
    registry: OosRegistry,
    *,
    oos_fraction: float = 0.2,
    min_oos_candles: int = 100,
) -> Splits:
    """Fix (or look up) where the locked period starts and cut the history there."""
    ordered = sorted(candles, key=lambda c: c.ts)
    n = len(ordered)
    claim = registry.get(key)
    if claim is None:
        start_index = max(n - max(int(n * oos_fraction), min_oos_candles), 0)
        if start_index < MIN_CANDLES * 2:
            raise ValueError("not enough history to keep a locked out-of-sample period")
        registry.set_start(key, ordered[start_index].ts)
        oos_start = ordered[start_index].ts
    else:
        oos_start = claim.oos_start
        start_index = next((i for i, c in enumerate(ordered) if c.ts >= oos_start), n)
    tuning_segment = Segment("tuning", 0, start_index)
    oos_segment = Segment("oos", start_index, n)
    return Splits(
        tuning=ordered[:start_index],
        tuning_segment=tuning_segment,
        oos=LockedOos(ordered[start_index:], oos_segment, key, registry, oos_start),
    )


@dataclass(frozen=True, slots=True)
class Window:
    train: Segment
    test: Segment


def walk_forward_windows(
    n: int, train_size: int, test_size: int, step: int | None = None
) -> list[Window]:
    """Rolling windows over `n` candles: train, then the test that follows it, then slide by
    `step` (default: the test size, so the test windows tile the history without overlap)."""
    if train_size <= 0 or test_size <= 0:
        raise ValueError("train and test sizes must be positive")
    step = step or test_size
    windows = []
    start = 0
    while start + train_size + test_size <= n:
        train = Segment("train", start, start + train_size)
        test = Segment("test", start + train_size, start + train_size + test_size)
        windows.append(Window(train, test))
        start += step
    return windows


def candles_for(segment: Segment, candles: list[RawCandle]) -> list[RawCandle]:
    """The candles to feed the engine to evaluate `segment`: the segment plus the history before
    it that the indicators need to warm up. Decisions start exactly at the segment's start."""
    first = max(segment.start - MIN_CANDLES, 0)
    return candles[first : segment.end]
