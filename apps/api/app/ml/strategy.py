"""The model as a backtest strategy: it only GATES entries. It never sizes or places orders.

The strategy says BUY when the model's win probability for the next trade is at least the
declared threshold; otherwise HOLD. The risk engine still plans the stop and target, sizes the
trade and can veto it, exactly as for the rules. The model never emits SELL: a trade ends at its
stop or target (the same two exits the labels were defined on).

Causality, the part that must not be wrong. A model is trained on rows whose label finished
BEFORE a cutoff, and the cutoffs are fixed times (every `test_rows` rows of the CONTEXT, the
tuning region the model is allowed to learn from). A candle at time ts is scored by the model
with the latest cutoff at or before ts; after the end of the context (the locked period) it is
scored by one frozen model trained on the whole context. So a candle's probability depends only
on data from before it, however much of the series you give the strategy, and the leakage check
(cut the history, compare) passes.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

import numpy as np

from app.analysis.features import FeatureTable, compute_features
from app.analysis.indicators import CandleSeries
from app.backtest.registry import StrategyDef
from app.data.models import SignalAction
from app.ml.dataset import Dataset, build_dataset, feature_matrix
from app.ml.protocol import ENTRY_THRESHOLD, STRATEGY_NAME
from app.ml.train import MIN_CLASS_ROWS, fit
from app.signals.rules import Decision, Reason

NAN = float("nan")


class ModelBank:
    """Models by training cutoff, trained lazily and cached."""

    def __init__(self, context: CandleSeries, min_train_rows: int, test_rows: int) -> None:
        self.times = context.times
        self.data: Dataset = build_dataset(context)
        self._label_end_times = [self.times[int(i)] for i in self.data.label_end]
        starts = range(min_train_rows, len(self.data), test_rows)
        self.cutoffs: list[datetime] = [self.times[int(self.data.index[r])] for r in starts]
        self._cache: dict[datetime | None, Any] = {}

    def _train(self, cutoff: datetime | None) -> Any:
        if cutoff is None:  # after the context: everything with a finished label
            rows = np.arange(len(self.data))
        else:
            rows = np.array(
                [i for i, t in enumerate(self._label_end_times) if t < cutoff], dtype=np.int64
            )
        y = self.data.y[rows]
        if len(rows) == 0 or min(int((y == 0).sum()), int((y == 1).sum())) < MIN_CLASS_ROWS:
            return None
        return fit(self.data.x[rows], y)

    def cutoff_for(self, ts: datetime) -> datetime | str | None:
        """The cutoff whose model scores `ts`: a datetime, None (frozen final model) or "none"
        (too early in the context for any model)."""
        if ts > self.times[-1]:
            return None
        eligible = [c for c in self.cutoffs if c <= ts]
        return eligible[-1] if eligible else "none"

    def model(self, cutoff: datetime | None) -> Any:
        if cutoff not in self._cache:
            self._cache[cutoff] = self._train(cutoff)
        return self._cache[cutoff]

    def probabilities(self, series: CandleSeries, x: np.ndarray) -> np.ndarray:
        proba = np.full(len(series), NAN)
        groups: dict[datetime | None, list[int]] = {}
        for t, ts in enumerate(series.times):
            cutoff = self.cutoff_for(ts)
            if cutoff == "none" or not np.isfinite(x[t]).all():
                continue
            groups.setdefault(cutoff, []).append(t)  # type: ignore[arg-type]
        for cutoff, idx in groups.items():
            model = self.model(cutoff)
            if model is not None:
                proba[idx] = model.predict_proba(x[idx])[:, 1]
        return proba


def make_strategy(
    context: CandleSeries,
    min_train_rows: int,
    test_rows: int,
    threshold: float = ENTRY_THRESHOLD,
) -> StrategyDef:
    bank = ModelBank(context, min_train_rows, test_rows)

    def features(series: CandleSeries) -> FeatureTable:
        table = compute_features(series)
        table["ml_proba"] = bank.probabilities(series, feature_matrix(series, table))
        return table

    def decide(table: FeatureTable) -> Decision:
        p = float(table["ml_proba"][-1])
        atr = float(table["atr"][-1])
        if not (np.isfinite(p) and np.isfinite(atr)):
            return Decision(
                SignalAction.HOLD,
                Decimal("0"),
                [Reason("ml_unavailable", "No model probability yet.", "neutral", 0.0)],
                {"atr": atr},
            )
        if p >= threshold:
            reason = Reason(
                "ml_probability",
                f"Model gives {p:.0%} that the target is hit before the stop "
                f"(entry threshold {threshold:.0%}).",
                "buy",
                1.0,
            )
            action = SignalAction.BUY
        else:
            reason = Reason(
                "ml_below_threshold",
                f"Model probability {p:.0%} is under the {threshold:.0%} threshold.",
                "neutral",
                0.0,
            )
            action = SignalAction.HOLD
        return Decision(
            action,
            Decimal(str(round(min(max(p, 0.0), 1.0), 4))),
            [reason],
            {"atr": atr, "ml_proba": p},
        )

    return StrategyDef(STRATEGY_NAME, features, decide)
