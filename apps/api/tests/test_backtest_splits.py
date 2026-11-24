"""Walk-forward windows and the lock on out-of-sample data."""

import itertools
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.analysis.features import MIN_CANDLES
from app.backtest.splits import (
    LockedOos,
    MemoryRegistry,
    OosKey,
    OosLockedError,
    Segment,
    candles_for,
    make_splits,
    walk_forward_windows,
)
from app.data.adapters.base import RawCandle

T0 = datetime(2026, 1, 1, tzinfo=UTC)
KEY = OosKey("BTC/USDT", "1h", "rules-v2")


def history(n: int) -> list[RawCandle]:
    out = []
    for i in range(n):
        price = Decimal(100 + i % 7)
        out.append(RawCandle(T0 + timedelta(hours=i), price, price, price, price, Decimal(1)))
    return out


def test_windows_tile_the_history_without_overlapping_tests() -> None:
    windows = walk_forward_windows(1000, train_size=400, test_size=100)

    assert len(windows) == 6
    for w in windows:
        assert w.train.end == w.test.start  # the test comes right after its training
        assert len(w.train) == 400 and len(w.test) == 100
    tests = [(w.test.start, w.test.end) for w in windows]
    assert all(a_end <= b_start for (_, a_end), (b_start, _) in itertools.pairwise(tests))
    assert windows[-1].test.end <= 1000  # never past the data


def test_a_step_smaller_than_the_test_makes_overlapping_windows() -> None:
    windows = walk_forward_windows(600, 300, 100, step=50)

    assert windows[1].train.start - windows[0].train.start == 50


def test_not_enough_data_gives_no_windows_and_bad_sizes_are_refused() -> None:
    assert walk_forward_windows(100, 80, 40) == []
    with pytest.raises(ValueError):
        walk_forward_windows(100, 0, 10)


def test_the_locked_period_is_the_last_fifth_and_fixed_by_its_start_time() -> None:
    reg = MemoryRegistry()
    data = history(1000)

    splits = make_splits(data, KEY, reg)

    assert len(splits.tuning) == 800 and splits.tuning_segment == Segment("tuning", 0, 800)
    assert splits.oos.oos_start == data[800].ts
    assert splits.tuning[-1].ts < splits.oos.oos_start  # tuning never touches the locked data
    # New data arrives: the locked period starts at the same time and simply grows.
    again = make_splits(history(1200), KEY, reg)
    assert len(again.tuning) == 800 and again.oos.oos_start == data[800].ts


def test_the_locked_candles_are_not_exposed_without_unlock() -> None:
    splits = make_splits(history(1000), KEY, MemoryRegistry())

    assert isinstance(splits.oos, LockedOos)
    assert "locked" in repr(splits.oos)
    public = [name for name in dir(splits.oos) if not name.startswith("_")]
    assert set(public) <= {"oos_start", "segment", "unlock"}  # no way to read candles directly
    assert not hasattr(splits.oos, "__dict__")  # __slots__: nothing sneaks in either


def test_one_configuration_may_judge_the_period_again_but_a_second_may_not() -> None:
    reg = MemoryRegistry()
    splits = make_splits(history(1000), KEY, reg)

    first = splits.oos.unlock("config-A")
    again = splits.oos.unlock("config-A")  # reproducing the same result is fine
    assert len(first) == len(again) == 200

    with pytest.raises(OosLockedError, match="config-A"):
        splits.oos.unlock("config-B")  # tuning on the locked period: refused

    # A different strategy or instrument has its own locked period.
    other = make_splits(history(1000), OosKey("ETH/USDT", "1h", "rules-v2"), reg)
    assert len(other.oos.unlock("config-B")) == 200


def test_the_lock_holds_even_when_the_registry_is_rebuilt_from_a_stored_claim() -> None:
    reg = MemoryRegistry()
    make_splits(history(1000), KEY, reg).oos.unlock("config-A")

    # A new process: new splits object, same registry (in production it is the database).
    splits = make_splits(history(1100), KEY, reg)

    with pytest.raises(OosLockedError):
        splits.oos.unlock("config-B")


def test_too_little_history_cannot_keep_a_locked_period() -> None:
    with pytest.raises(ValueError, match="not enough history"):
        make_splits(history(150), KEY, MemoryRegistry())


def test_a_segment_comes_with_the_warm_up_history_before_it() -> None:
    data = history(1000)

    window = candles_for(Segment("test", 500, 600), data)

    assert len(window) == 100 + MIN_CANDLES
    assert window[MIN_CANDLES].ts == data[500].ts  # decisions start exactly at the segment
    assert candles_for(Segment("test", 10, 60), data)[0].ts == data[0].ts  # near the start


def _walk_data(n: int) -> list[RawCandle]:
    import numpy as np

    rng = np.random.default_rng(2)
    price = 100.0
    out = []
    for i in range(n):
        price *= 1 + rng.normal(0.0001, 0.01)
        out.append(
            RawCandle(
                T0 + timedelta(hours=i),
                Decimal(str(round(price, 4))),
                Decimal(str(round(price * 1.004, 4))),
                Decimal(str(round(price * 0.996, 4))),
                Decimal(str(round(price, 4))),
                Decimal(5),
            )
        )
    return out


def test_walk_forward_only_ever_sees_the_tuning_region() -> None:
    from app.backtest.engine import BacktestConfig
    from app.backtest.walkforward import walk_forward
    from app.data.models import SignalAction
    from app.signals.rules import Decision

    splits = make_splits(_walk_data(1000), KEY, MemoryRegistry())
    seen: list[datetime] = []

    def spy(view: dict[str, object]) -> Decision:
        seen.append(T0)  # the strategy ran
        return Decision(SignalAction.HOLD, Decimal(0), [], {})

    results = walk_forward(
        splits,
        BacktestConfig("BTC/USDT", "1h"),
        train_size=300,
        test_size=100,
        strategy=spy,  # type: ignore[arg-type]
    )

    assert results and seen
    for r in results:
        assert r.result.times[-1] < splits.oos.oos_start  # no window reaches the locked period


def test_judging_the_locked_period_is_one_configuration_only() -> None:
    from app.backtest.engine import BacktestConfig
    from app.backtest.walkforward import judge_oos, run_on_tuning

    splits = make_splits(_walk_data(1000), KEY, MemoryRegistry())
    config = BacktestConfig("BTC/USDT", "1h")

    tuning = run_on_tuning(splits, config)  # tuning runs never touch the lock
    verdict = judge_oos(splits, config)
    again = judge_oos(splits, config)  # the same configuration can be re-run

    assert tuning.times[-1] < splits.oos.oos_start
    assert verdict.times[0] < splits.oos.oos_start <= verdict.times[-1]  # warm-up, then locked
    assert [t.to_dict() for t in verdict.trades] == [t.to_dict() for t in again.trades]
    assert all(t.entry_ts >= splits.oos.oos_start for t in verdict.trades)  # decisions only there
    with pytest.raises(OosLockedError):
        judge_oos(splits, BacktestConfig("BTC/USDT", "1h", fee_pct=Decimal("0.05")))
