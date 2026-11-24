"""Training with purged walk-forward validation, tracked in MLflow.

Why "purged": a label at candle t looks `HORIZON` candles ahead, so a training row near the test
window has a label that depends on candles inside the test window. Training on it would leak the
test period's prices into the model. So the training rows for a fold are only those whose label
ended BEFORE the first test candle (a gap of one horizon), which is what `purged_folds` returns.

The model parameters are DECLARED here, before any result was seen, and are not tuned: judging a
model on data used to choose its settings proves nothing. lightgbm, scikit-learn and mlflow
(the `ml` dependency group) are imported lazily, so the rest of the app works without them.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from app.ml.dataset import Dataset

PARAMS: dict[str, Any] = {
    "n_estimators": 200,
    "learning_rate": 0.03,
    "num_leaves": 15,
    "min_child_samples": 50,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "reg_lambda": 5.0,
    "random_state": 7,
    "deterministic": True,
    "force_row_wise": True,
    "n_jobs": 1,
    "verbose": -1,
}
MIN_TRAIN_ROWS = 1000
TEST_ROWS = 500
MIN_CLASS_ROWS = 20  # a fold needs this many of each class in training to fit anything useful


@dataclass(frozen=True, slots=True)
class Fold:
    train: np.ndarray  # row numbers in the dataset
    test: np.ndarray


def purged_folds(
    data: Dataset, *, min_train_rows: int = MIN_TRAIN_ROWS, test_rows: int = TEST_ROWS
) -> list[Fold]:
    """Expanding-window folds. Test blocks are consecutive and do not overlap; each fold trains
    only on rows whose label finished before the block's first candle."""
    folds: list[Fold] = []
    n = len(data)
    start = min_train_rows
    while start + test_rows <= n:
        test = np.arange(start, start + test_rows)
        first_test_candle = data.index[start]
        train = np.flatnonzero(data.label_end < first_test_candle)
        if len(train) >= min_train_rows:
            folds.append(Fold(train, test))
        start += test_rows
    return folds


def fit(x: np.ndarray, y: np.ndarray, params: dict[str, Any] | None = None) -> Any:
    from lightgbm import LGBMClassifier

    model = LGBMClassifier(**(params or PARAMS))
    model.fit(x, y)
    return model


@dataclass(frozen=True, slots=True)
class FoldMetrics:
    rows: int
    base_rate: float
    auc: float | None
    brier: float
    brier_base: float  # always predicting the training base rate


@dataclass(slots=True)
class WalkForwardResult:
    proba: np.ndarray  # one per dataset row; NaN where the row was never in a test block
    folds: list[FoldMetrics] = field(default_factory=list)

    @property
    def mean_auc(self) -> float | None:
        values = [f.auc for f in self.folds if f.auc is not None]
        return float(np.mean(values)) if values else None


def walk_forward_predict(
    data: Dataset,
    params: dict[str, Any] | None = None,
    *,
    min_train_rows: int = MIN_TRAIN_ROWS,
    test_rows: int = TEST_ROWS,
) -> WalkForwardResult:
    from sklearn.metrics import brier_score_loss, roc_auc_score

    proba = np.full(len(data), np.nan)
    metrics: list[FoldMetrics] = []
    for fold in purged_folds(data, min_train_rows=min_train_rows, test_rows=test_rows):
        y_train = data.y[fold.train]
        if min(int((y_train == 0).sum()), int((y_train == 1).sum())) < MIN_CLASS_ROWS:
            continue
        model = fit(data.x[fold.train], y_train, params)
        p = np.asarray(model.predict_proba(data.x[fold.test])[:, 1], dtype=np.float64)
        proba[fold.test] = p
        y = data.y[fold.test]
        base = float(y_train.mean())
        metrics.append(
            FoldMetrics(
                rows=len(fold.test),
                base_rate=float(y.mean()),
                auc=float(roc_auc_score(y, p)) if len(set(y.tolist())) == 2 else None,
                brier=float(brier_score_loss(y, p)),
                brier_base=float(brier_score_loss(y, np.full(len(y), base))),
            )
        )
    return WalkForwardResult(proba, metrics)


def log_to_mlflow(
    name: str,
    params: dict[str, Any],
    result: WalkForwardResult,
    tags: dict[str, str] | None = None,
    tracking_uri: str | None = None,
) -> str:
    """Record the run (parameters, per-fold and mean metrics) and return the MLflow run id."""
    import mlflow

    uri = tracking_uri or os.environ.get("MLFLOW_TRACKING_URI")
    if uri is None:
        Path("mlruns").mkdir(exist_ok=True)  # git-ignored
        uri = "sqlite:///mlruns/mlflow.db"  # MLflow no longer allows its file backend by default
    mlflow.set_tracking_uri(uri)
    mlflow.set_experiment("aitp-ml")
    with mlflow.start_run(run_name=name) as run:
        mlflow.log_params({k: str(v) for k, v in params.items()})
        if tags:
            mlflow.set_tags(tags)
        for step, fold in enumerate(result.folds):
            mlflow.log_metrics(
                {
                    "auc": fold.auc if fold.auc is not None else float("nan"),
                    "brier": fold.brier,
                    "brier_base": fold.brier_base,
                },
                step=step,
            )
        if result.mean_auc is not None:
            mlflow.log_metric("mean_auc", result.mean_auc)
        mlflow.log_metric("folds", len(result.folds))
        return str(run.info.run_id)
