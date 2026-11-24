"""Does the model know anything? Baselines, calibration and a comparison with the rules.

Everything here is computed from OUT-OF-FOLD probabilities (each from a model that never saw
its own period) on the tuning region only. Measures:

- AUC: 0.5 is a coin flip.
- Brier score of the model against three baselines: the training base rate, a coin flip
  (always 0.5, Brier 0.25) and, for context, the raw versus calibrated probabilities.
- Calibration: do rows given 40% win about 40%? Reported as a reliability table and the
  expected calibration error (ECE). A Platt-scaled version is fitted only on EARLIER folds'
  out-of-fold predictions whose labels had already finished (purged), never on its own fold.
- Precision at thresholds against the break-even win rate. With a 1.6:1 payoff the break-even
  is 1/2.6 = 38.5% before costs, and higher after them, which is the number that matters.
- The rules baseline: how often rules-v2 BUY signals hit their target on the same rows.
"""

import itertools
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.analysis.features import compute_features
from app.analysis.indicators import CandleSeries
from app.data.models import SignalAction
from app.ml.dataset import TARGET_ATR, Dataset, build_dataset
from app.ml.train import (
    MIN_TRAIN_ROWS,
    TEST_ROWS,
    Fold,
    WalkForwardResult,
    purged_folds,
    walk_forward_predict,
)
from app.signals.rules import evaluate

THRESHOLDS = (0.40, 0.45, 0.50, 0.55)
BINS = 10
ROUND_TRIP_COST_BPS = 20.0  # 0.10% fee each side, slippage ignored (a lower bound)


def breakeven_win_rate(atr_percent: float, cost_bps: float = ROUND_TRIP_COST_BPS) -> float:
    """The win rate at which a 1.0 ATR stop / 1.6 ATR target trade breaks even after costs.
    The cost in units of risk is cost / (ATR% in bps); EV = p(1.6 - c) - (1-p)(1 + c) = 0."""
    cost_r = cost_bps / (atr_percent * 100.0)
    return float((1.0 + cost_r) / (1.0 + TARGET_ATR))


@dataclass(frozen=True, slots=True)
class Bin:
    low: float
    high: float
    rows: int
    mean_predicted: float
    observed: float


def reliability(y: np.ndarray, p: np.ndarray, bins: int = BINS) -> tuple[list[Bin], float]:
    """Reliability table over equal-width probability bins and the expected calibration error."""
    edges = np.linspace(0.0, 1.0, bins + 1)
    out: list[Bin] = []
    ece = 0.0
    for lo, hi in itertools.pairwise(edges):
        mask = (p >= lo) & ((p < hi) if hi < 1.0 else (p <= hi))
        if not mask.any():
            continue
        item = Bin(
            float(lo), float(hi), int(mask.sum()), float(p[mask].mean()), float(y[mask].mean())
        )
        out.append(item)
        ece += item.rows / len(y) * abs(item.mean_predicted - item.observed)
    return out, float(ece)


def _logit(q: np.ndarray) -> np.ndarray:
    clipped = np.clip(q, 1e-6, 1 - 1e-6)
    return np.asarray(np.log(clipped / (1 - clipped)), dtype=np.float64)


def platt_walk_forward(data: Dataset, proba: np.ndarray, folds: list[Fold]) -> np.ndarray:
    """Calibrated probabilities. For each fold after the first, a logistic fit of the outcome
    on the logit of the raw probability, using only EARLIER folds' scored rows whose labels had
    finished before this fold began. The first fold stays NaN (nothing earlier to learn from)."""
    from sklearn.linear_model import LogisticRegression

    out = np.full(len(data), np.nan)
    for k, fold in enumerate(folds):
        if k == 0:
            continue
        first_candle = data.index[fold.test[0]]
        earlier = np.concatenate([f.test for f in folds[:k]])
        usable = earlier[(data.label_end[earlier] < first_candle) & np.isfinite(proba[earlier])]
        y = data.y[usable]
        if len(usable) < 200 or len(set(y.tolist())) < 2:
            continue
        model = LogisticRegression(C=1e6).fit(_logit(proba[usable]).reshape(-1, 1), y)
        out[fold.test] = model.predict_proba(_logit(proba[fold.test]).reshape(-1, 1))[:, 1]
    return out


@dataclass(slots=True)
class Evaluation:
    rows: int
    base_rate: float
    auc: float | None
    brier_model: float
    brier_calibrated: float | None
    brier_prior: float
    brier_coin: float
    ece_raw: float
    ece_calibrated: float | None
    breakeven: float
    reliability: list[Bin] = field(default_factory=list)
    thresholds: list[dict[str, Any]] = field(default_factory=list)
    rules_buy: dict[str, Any] = field(default_factory=dict)
    folds: int = 0

    @property
    def beats_baselines(self) -> bool:
        """The honest first question: better than the training base rate and a coin flip?"""
        return self.brier_model < min(self.brier_prior, self.brier_coin)


def rules_buy_precision(series: CandleSeries, data: Dataset, scored: np.ndarray) -> dict[str, Any]:
    """Among the scored rows where rules-v2 says BUY, how often did the target hit first?"""
    table = compute_features(series)
    hits, total = 0, 0
    for row in np.flatnonzero(scored):
        t = int(data.index[row])
        view = {name: values[: t + 1] for name, values in table.items()}
        if evaluate(view).action is SignalAction.BUY:
            total += 1
            hits += int(data.y[row])
    return {"signals": total, "win_rate": hits / total if total else None}


def evaluate_model(
    series: CandleSeries,
    data: Dataset | None = None,
    *,
    min_train_rows: int = MIN_TRAIN_ROWS,
    test_rows: int = TEST_ROWS,
) -> tuple[Evaluation, WalkForwardResult]:
    from sklearn.metrics import brier_score_loss, roc_auc_score

    data = data if data is not None else build_dataset(series)
    result = walk_forward_predict(data, min_train_rows=min_train_rows, test_rows=test_rows)
    folds = purged_folds(data, min_train_rows=min_train_rows, test_rows=test_rows)
    scored = np.isfinite(result.proba)
    if not scored.any():
        raise ValueError("no fold could be scored: not enough history")
    y, p = data.y[scored], result.proba[scored]
    calibrated = platt_walk_forward(data, result.proba, folds)
    cal_mask = np.isfinite(calibrated)
    train_rate = float(data.y[: int(np.flatnonzero(scored)[0])].mean())
    table = compute_features(series)
    atr_pct = float(np.nanmean(table["atr_percent"][data.index[scored]]))
    bins, ece = reliability(y, p)
    cal_ece = reliability(data.y[cal_mask], calibrated[cal_mask])[1] if cal_mask.any() else None
    breakeven = breakeven_win_rate(atr_pct)
    evaluation = Evaluation(
        rows=int(scored.sum()),
        base_rate=float(y.mean()),
        auc=float(roc_auc_score(y, p)) if len(set(y.tolist())) == 2 else None,
        brier_model=float(brier_score_loss(y, p)),
        brier_calibrated=float(brier_score_loss(data.y[cal_mask], calibrated[cal_mask]))
        if cal_mask.any()
        else None,
        brier_prior=float(brier_score_loss(y, np.full(len(y), train_rate))),
        brier_coin=float(brier_score_loss(y, np.full(len(y), 0.5))),
        ece_raw=ece,
        ece_calibrated=cal_ece,
        breakeven=breakeven,
        reliability=bins,
        folds=len(result.folds),
    )
    for threshold in THRESHOLDS:
        mask = p >= threshold
        evaluation.thresholds.append(
            {
                "threshold": threshold,
                "rows": int(mask.sum()),
                "win_rate": float(y[mask].mean()) if mask.any() else None,
            }
        )
    evaluation.rules_buy = rules_buy_precision(series, data, scored)
    return evaluation, result
