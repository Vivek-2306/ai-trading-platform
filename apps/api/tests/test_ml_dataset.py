"""Labels follow the backtest's stop/target rules; features and labels never use the future."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np

from app.analysis.features import find_lookahead
from app.analysis.indicators import CandleSeries
from app.backtest.splits import MemoryRegistry, OosKey, make_splits
from app.data.adapters.base import RawCandle
from app.ml.dataset import (
    FEATURE_NAMES,
    HORIZON,
    build_dataset,
    feature_matrix,
    label_trade,
)

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def candle(i: int, o: float, h: float, low: float, c: float) -> RawCandle:
    return RawCandle(
        T0 + timedelta(hours=i), Decimal(str(o)), Decimal(str(h)), Decimal(str(low)),
        Decimal(str(c)), Decimal("10"),
    )  # fmt: skip


def flat(n: int = 10, price: float = 100.0) -> list[RawCandle]:
    return [candle(i, price, price + 0.1, price - 0.1, price) for i in range(n)]


def series_with(
    overrides: dict[int, tuple[float, float, float, float]], n: int = 10
) -> CandleSeries:
    data = flat(n)
    for i, (o, h, low, c) in overrides.items():
        data[i] = candle(i, o, h, low, c)
    return CandleSeries.from_candles(data)


def walk(n: int = 600, seed: int = 3) -> CandleSeries:
    rng = np.random.default_rng(seed)
    price, out = 100.0, []
    for i in range(n):
        price *= 1 + rng.normal(0, 0.01)
        out.append(
            candle(i, price, price * 1.006, price * 0.994, price * (1 + rng.normal(0, 0.002)))
        )
    return CandleSeries.from_candles(out)


def test_target_before_stop_is_a_win() -> None:
    # fill at open of candle 3 (100); atr 1 -> stop 99, target 101.6; candle 4 trades through 101.6
    s = series_with({4: (100, 102, 99.5, 101)})

    assert label_trade(s, 2, atr=1.0, horizon=5) == 1


def test_stop_before_target_is_a_loss() -> None:
    s = series_with({4: (100, 100.5, 98.5, 99), 5: (99, 103, 99, 102)})

    assert label_trade(s, 2, atr=1.0, horizon=5) == 0


def test_a_candle_touching_both_counts_as_a_stop() -> None:
    s = series_with({4: (100, 103, 98, 100)})

    assert label_trade(s, 2, atr=1.0, horizon=5) == 0


def test_touching_the_target_exactly_is_not_a_fill() -> None:
    s = series_with({4: (100, 101.6, 99.5, 101)})  # high == target: must trade THROUGH it

    assert label_trade(s, 2, atr=1.0, horizon=5) == 0


def test_a_timeout_is_a_zero_and_an_unknown_horizon_is_not_labelled() -> None:
    s = series_with({})

    assert label_trade(s, 2, atr=1.0, horizon=5) == 0
    assert label_trade(s, 6, atr=1.0, horizon=5) is None  # 6 + 5 reaches past the data
    assert label_trade(s, 2, atr=float("nan"), horizon=5) is None


def test_the_dataset_only_contains_complete_rows_and_records_label_reach() -> None:
    series = walk()

    data = build_dataset(series)

    assert data.x.shape == (len(data), len(FEATURE_NAMES)) and len(data) > 400
    assert np.isfinite(data.x).all() and set(np.unique(data.y)) <= {0, 1}
    assert data.index.max() + HORIZON < len(series)  # no label reaches past the data
    assert (data.label_end - data.index == HORIZON).all()
    assert 0.05 < data.y.mean() < 0.95  # both outcomes occur


def test_features_never_use_a_later_candle() -> None:
    series = walk(300)

    def compute(s: CandleSeries) -> dict[str, np.ndarray]:
        m = feature_matrix(s)
        return {name: m[:, i] for i, name in enumerate(FEATURE_NAMES)}

    assert find_lookahead(compute, series, checkpoints=list(range(60, 300, 13))) == []


def test_a_row_decided_at_t_is_unchanged_when_later_candles_are_removed() -> None:
    series = walk(400)
    full = build_dataset(series)
    cut = build_dataset(series.upto(300))

    # rows labelled in the cut data have the same features and labels as in the full data
    shared = np.isin(full.index, cut.index)
    assert np.allclose(full.x[shared][: len(cut)], cut.x)
    assert (full.y[shared][: len(cut)] == cut.y).all()


def test_the_tuning_candles_hold_no_label_that_reaches_the_locked_period() -> None:
    candles = [candle(i, 100 + i % 7, 101 + i % 7, 99 + i % 7, 100 + i % 5) for i in range(700)]
    splits = make_splits(candles, OosKey("BTC/USDT", "1h", "ml"), MemoryRegistry())

    data = build_dataset(CandleSeries.from_candles(splits.tuning))

    assert data.label_end.max() < len(splits.tuning)  # every label is inside the tuning region
