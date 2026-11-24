"""The strategies a backtest can run, by name (the name is part of the lock identity)."""

from collections.abc import Callable
from dataclasses import dataclass

from app.analysis.features import FeatureTable, compute_features
from app.analysis.indicators import CandleSeries
from app.scalping.strategies import ema_cross, range_breakout, scalp_features, vwap_pullback
from app.signals.rules import Decision, evaluate

FeaturesFn = Callable[[CandleSeries], FeatureTable]
DecideFn = Callable[[FeatureTable], Decision]


@dataclass(frozen=True, slots=True)
class StrategyDef:
    name: str
    features: FeaturesFn
    decide: DecideFn


def _rules(table: FeatureTable) -> Decision:
    return evaluate(table)


STRATEGIES: dict[str, StrategyDef] = {
    d.name: d
    for d in (
        StrategyDef("rules-v2", compute_features, _rules),
        StrategyDef("scalp-ema-cross", scalp_features, ema_cross),
        StrategyDef("scalp-vwap-pullback", scalp_features, vwap_pullback),
        StrategyDef("scalp-breakout", scalp_features, range_breakout),
    )
}


def resolve(name: str) -> StrategyDef:
    try:
        return STRATEGIES[name]
    except KeyError:
        raise ValueError(f"unknown strategy {name!r}; choose from {sorted(STRATEGIES)}") from None
