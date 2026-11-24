"""Purged walk-forward folds (pure) and training/tracking (needs the `ml` group)."""

import itertools
from pathlib import Path

import numpy as np
import pytest

from app.ml.dataset import HORIZON, Dataset
from app.ml.train import Fold, purged_folds


def synthetic(n: int = 4000, signal: float = 2.0, seed: int = 1) -> Dataset:
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 12))
    p = 1 / (1 + np.exp(-(signal * x[:, 0] - 0.5)))
    y = (rng.uniform(size=n) < p).astype(np.int8)
    index = np.arange(n, dtype=np.int64) + 50
    return Dataset(index, x, y, index + HORIZON)


def test_a_training_label_never_reaches_into_its_test_block() -> None:
    data = synthetic()

    folds = purged_folds(data)

    assert len(folds) >= 5
    for fold in folds:
        first_test_candle = data.index[fold.test[0]]
        assert data.label_end[fold.train].max() < first_test_candle
        assert fold.train.max() < fold.test[0]  # train is the past only


def test_the_purge_leaves_a_gap_of_one_horizon() -> None:
    data = synthetic()

    fold = purged_folds(data)[0]

    gap = data.index[fold.test[0]] - data.index[fold.train.max()]
    assert gap > HORIZON  # the rows inside the horizon before the test block are dropped


def test_test_blocks_are_consecutive_and_never_overlap() -> None:
    folds = purged_folds(synthetic())

    for a, b in itertools.pairwise(folds):
        assert b.test[0] == a.test[-1] + 1
    assert all(isinstance(f, Fold) for f in folds)


def test_a_dataset_too_small_for_one_fold_gives_none() -> None:
    assert purged_folds(synthetic(900)) == []


def test_the_model_learns_a_real_signal_and_not_noise() -> None:
    pytest.importorskip("lightgbm")
    pytest.importorskip("sklearn")
    from app.ml.train import walk_forward_predict

    real = walk_forward_predict(synthetic(signal=2.0))
    noise = walk_forward_predict(synthetic(signal=0.0))

    assert real.mean_auc is not None and real.mean_auc > 0.7
    assert noise.mean_auc is not None and abs(noise.mean_auc - 0.5) < 0.05
    scored = np.isfinite(real.proba)
    assert not scored[:1000].any()  # rows before the first test block are never scored
    assert scored.sum() >= 2500 and scored[-500:].all()


def test_training_is_deterministic() -> None:
    pytest.importorskip("lightgbm")
    pytest.importorskip("sklearn")
    from app.ml.train import walk_forward_predict

    a = walk_forward_predict(synthetic(2500))
    b = walk_forward_predict(synthetic(2500))

    assert np.array_equal(a.proba, b.proba, equal_nan=True)


# MLflow's SQL store uses a loader option that SQLAlchemy 2.1 deprecates (a library issue).
@pytest.mark.filterwarnings("ignore:The ``noload`` loader strategy is deprecated")
def test_runs_are_logged_to_mlflow(tmp_path: Path) -> None:
    pytest.importorskip("lightgbm")
    pytest.importorskip("sklearn")
    pytest.importorskip("mlflow")
    from mlflow.tracking import MlflowClient

    from app.ml.train import PARAMS, log_to_mlflow, walk_forward_predict

    result = walk_forward_predict(synthetic(2500))
    uri = f"sqlite:///{tmp_path}/mlflow.db"

    run_id = log_to_mlflow("test-run", PARAMS, result, {"stage": "test"}, tracking_uri=uri)

    run = MlflowClient(uri).get_run(run_id)
    assert run.data.params["num_leaves"] == "15" and run.data.tags["stage"] == "test"
    assert run.data.metrics["mean_auc"] == pytest.approx(result.mean_auc)
    assert run.data.metrics["folds"] == len(result.folds)
