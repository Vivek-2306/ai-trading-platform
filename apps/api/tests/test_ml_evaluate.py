"""Baselines, calibration and break-even maths."""

import numpy as np
import pytest

from app.ml.dataset import build_dataset
from app.ml.evaluate import breakeven_win_rate, reliability
from tests.test_ml_dataset import walk


def test_breakeven_rises_with_costs_relative_to_risk() -> None:
    # Free trading: 1 / 2.6. With costs worth a third of the risk the bar is higher.
    assert breakeven_win_rate(atr_percent=1e9) == pytest.approx(1 / 2.6, abs=1e-6)
    cheap, dear = breakeven_win_rate(2.0), breakeven_win_rate(0.2)
    assert 1 / 2.6 < cheap < dear < 1.0
    assert breakeven_win_rate(0.5) == pytest.approx((1 + 20 / 50) / 2.6)


def test_a_perfectly_calibrated_forecast_has_zero_error() -> None:
    p = np.repeat([0.25, 0.75], 400)
    y = np.concatenate([np.repeat([1, 0, 0, 0], 100), np.repeat([1, 1, 1, 0], 100)])

    bins, ece = reliability(y, p)

    assert ece == pytest.approx(0.0)
    assert [(b.rows, round(b.observed, 2)) for b in bins] == [(400, 0.25), (400, 0.75)]


def test_an_overconfident_forecast_shows_a_calibration_error() -> None:
    p = np.full(1000, 0.9)
    y = np.repeat([1, 0], 500)  # actually wins half the time

    assert reliability(y, p)[1] == pytest.approx(0.4)


def test_probability_one_lands_in_the_last_bin() -> None:
    bins, _ = reliability(np.array([1, 1]), np.array([1.0, 1.0]))

    assert bins[0].high == 1.0 and bins[0].rows == 2


def test_noise_is_reported_as_no_better_than_the_baselines() -> None:
    pytest.importorskip("lightgbm")
    pytest.importorskip("sklearn")
    from app.ml.evaluate import evaluate_model

    series = walk(4000, seed=5)

    ev, _ = evaluate_model(series, build_dataset(series), min_train_rows=800, test_rows=400)

    assert ev.auc is not None and abs(ev.auc - 0.5) < 0.08  # a random walk has no signal
    assert not ev.beats_baselines
    assert ev.rows > 1000 and ev.folds >= 3
    assert {t["threshold"] for t in ev.thresholds} == {0.40, 0.45, 0.50, 0.55}
    assert ev.rules_buy["signals"] >= 0


def test_calibration_never_uses_its_own_fold_or_unfinished_labels() -> None:
    pytest.importorskip("lightgbm")
    pytest.importorskip("sklearn")
    from app.ml.evaluate import platt_walk_forward
    from app.ml.train import purged_folds, walk_forward_predict

    data = build_dataset(walk(4000, seed=6))
    folds = purged_folds(data, min_train_rows=800, test_rows=400)
    result = walk_forward_predict(data, min_train_rows=800, test_rows=400)

    calibrated = platt_walk_forward(data, result.proba, folds)

    assert np.isnan(calibrated[folds[0].test]).all()  # the first fold has nothing earlier
    assert np.isfinite(calibrated[folds[-1].test]).all()


def _evaluation(brier: float, win: float, breakeven: float = 0.45):  # type: ignore[no-untyped-def]
    from app.ml.evaluate import Evaluation

    return Evaluation(
        rows=1000, base_rate=0.4, auc=0.55, brier_model=brier, brier_calibrated=None,
        brier_prior=0.24, brier_coin=0.25, ece_raw=0.02, ece_calibrated=None,
        breakeven=breakeven, thresholds=[{"threshold": 0.5, "rows": 500, "win_rate": win}],
    )  # fmt: skip


def test_the_verdict_needs_both_the_baselines_and_the_break_even() -> None:
    pytest.importorskip("sklearn")
    from app.ml.report import verdict

    good = {("BTC/USDT", "1h"): _evaluation(0.23, 0.50)}
    weak = {("BTC/USDT", "1h"): _evaluation(0.25, 0.40)}

    assert verdict(good) == (True, [])
    ships, reasons = verdict(weak)
    assert not ships and len(reasons) == 2
    assert "not better than the base rate" in reasons[0] and "break-even" in reasons[1]
