"""What counts as "the same configuration" for the out-of-sample lock.

The settings in `BacktestConfig` are not the whole strategy: the rules' thresholds and logic, the
risk engine and the engine's own fill model all change results. If the lock only looked at the
settings, someone could edit the rules and "re-judge" the locked period under an unchanged
config, which is exactly tuning on it. So the identity includes a fingerprint of that code:
change any of it and the configuration is a different one.
"""

import hashlib
from functools import lru_cache
from pathlib import Path

from app.signals.rules import RULE_VERSION, RuleConfig

_APP = Path(__file__).resolve().parents[1]
# The code that decides, sizes and fills trades.
_FILES = (
    "signals/rules.py",
    "risk/plan.py",
    "risk/sizing.py",
    "risk/veto.py",
    "analysis/indicators.py",
    "analysis/features.py",
    "backtest/engine.py",
    "backtest/registry.py",
    "scalping/strategies.py",
)


@lru_cache
def strategy_fingerprint() -> str:
    digest = hashlib.sha256(RULE_VERSION.encode())
    digest.update(repr(RuleConfig()).encode())
    for name in _FILES:
        digest.update((_APP / name).read_bytes())
    return digest.hexdigest()[:16]
