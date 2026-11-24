"""Rule-based signals: plain, tested rules that vote, and a decision that explains itself.

This is the deterministic core (no AI, no model). Each rule looks at indicator values for the
newest closed candle and votes BUY or SELL with a weight and a reason in plain English. The
decision is then:

- NO_TRADE when there is not enough data, volatility is extreme, indicators conflict, or the
  agreement is too weak. NO_TRADE is a valid and common answer.
- BUY / SELL when one side clearly leads and the other is quiet.
- HOLD otherwise (nothing decisive either way).

Confidence is how much of the available rule weight agrees with the leading side (0 to 1). It
is an agreement score, not a probability: it is calibrated against backtests later (Phase 9).
BUY here means "conditions favour holding or entering long"; the platform is long-only spot.
"""

import math
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.analysis.features import FeatureTable, latest
from app.data.models import SignalAction

RULE_VERSION = "rules-v1"


@dataclass(frozen=True, slots=True)
class RuleConfig:
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    percent_b_low: float = 0.05
    percent_b_high: float = 0.95
    # Skip when the average candle range is this many percent of price (a panic or a glitch).
    max_atr_percent: float = 8.0
    # Score on the leading side needed to act, and the most the other side may have.
    act_score: float = 3.0
    quiet_score: float = 1.0
    # Both sides at least this strong means the indicators disagree.
    conflict_score: float = 1.5
    min_confidence: float = 0.55


@dataclass(frozen=True, slots=True)
class Reason:
    code: str
    text: str
    direction: str  # "buy", "sell", "neutral" or "info"
    weight: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "text": self.text,
            "direction": self.direction,
            "weight": self.weight,
        }


@dataclass(frozen=True, slots=True)
class Decision:
    action: SignalAction
    confidence: Decimal
    reasons: list[Reason]
    inputs: dict[str, float | None]
    buy_score: float = 0.0
    sell_score: float = 0.0
    rule_version: str = RULE_VERSION
    summary: str = field(default="")


def _confidence(value: float) -> Decimal:
    clamped = min(max(value, 0.0), 1.0)
    return Decimal(str(clamped)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _vote_rules(
    f: dict[str, float | None], prev: dict[str, float | None], cfg: RuleConfig
) -> list[Reason]:
    """Every rule whose inputs are available, with its vote."""
    reasons: list[Reason] = []

    def have(*names: str) -> bool:
        return all(f.get(n) is not None for n in names)

    if have("ema_fast", "ema_slow"):
        fast, slow = f["ema_fast"], f["ema_slow"]
        assert fast is not None and slow is not None
        if fast > slow:
            reasons.append(
                Reason(
                    "trend_up",
                    f"Fast average ({fast:.4g}) is above the slow one ({slow:.4g}): uptrend.",
                    "buy",
                    2.0,
                )
            )
        elif fast < slow:
            reasons.append(
                Reason(
                    "trend_down",
                    f"Fast average ({fast:.4g}) is below the slow one ({slow:.4g}): downtrend.",
                    "sell",
                    2.0,
                )
            )
    if have("close", "sma_slow"):
        close, sma = f["close"], f["sma_slow"]
        assert close is not None and sma is not None
        if close > sma:
            reasons.append(
                Reason(
                    "above_sma",
                    f"Price ({close:.4g}) is above its {50}-candle average ({sma:.4g}).",
                    "buy",
                    1.0,
                )
            )
        elif close < sma:
            reasons.append(
                Reason(
                    "below_sma",
                    f"Price ({close:.4g}) is below its {50}-candle average ({sma:.4g}).",
                    "sell",
                    1.0,
                )
            )
    if have("macd_hist"):
        hist = f["macd_hist"]
        assert hist is not None
        before = prev.get("macd_hist")
        if hist > 0 and (before is None or hist >= before):
            reasons.append(
                Reason("macd_up", "MACD momentum is positive and not fading.", "buy", 1.0)
            )
        elif hist < 0 and (before is None or hist <= before):
            reasons.append(
                Reason("macd_down", "MACD momentum is negative and not recovering.", "sell", 1.0)
            )
    if have("rsi"):
        rsi = f["rsi"]
        assert rsi is not None
        if rsi < cfg.rsi_oversold:
            reasons.append(
                Reason(
                    "rsi_oversold",
                    f"RSI is {rsi:.1f}, oversold (below {cfg.rsi_oversold:.0f}).",
                    "buy",
                    1.0,
                )
            )
        elif rsi > cfg.rsi_overbought:
            reasons.append(
                Reason(
                    "rsi_overbought",
                    f"RSI is {rsi:.1f}, overbought (above {cfg.rsi_overbought:.0f}).",
                    "sell",
                    1.0,
                )
            )
    if have("percent_b"):
        pb = f["percent_b"]
        assert pb is not None
        if pb < cfg.percent_b_low:
            reasons.append(
                Reason("below_band", "Price is at or below the lower Bollinger band.", "buy", 1.0)
            )
        elif pb > cfg.percent_b_high:
            reasons.append(
                Reason("above_band", "Price is at or above the upper Bollinger band.", "sell", 1.0)
            )
    if have("close", "vwap"):
        close, vwap = f["close"], f["vwap"]
        assert close is not None and vwap is not None
        if close > vwap:
            reasons.append(
                Reason(
                    "above_vwap",
                    f"Price is above the volume-weighted average ({vwap:.4g}).",
                    "buy",
                    0.5,
                )
            )
        elif close < vwap:
            reasons.append(
                Reason(
                    "below_vwap",
                    f"Price is below the volume-weighted average ({vwap:.4g}).",
                    "sell",
                    0.5,
                )
            )
    return reasons


def _available_weight(f: dict[str, float | None]) -> float:
    """Total weight of the rules that could vote (their inputs exist), whether or not they did."""
    total = 0.0
    for names, weight in (
        (("ema_fast", "ema_slow"), 2.0),
        (("close", "sma_slow"), 1.0),
        (("macd_hist",), 1.0),
        (("rsi",), 1.0),
        (("percent_b",), 1.0),
        (("close", "vwap"), 0.5),
    ):
        if all(f.get(n) is not None for n in names):
            total += weight
    return total


def _no_trade(
    reasons: list[Reason],
    inputs: dict[str, float | None],
    summary: str,
    confidence: float = 0.0,
    buy: float = 0.0,
    sell: float = 0.0,
) -> Decision:
    return Decision(
        SignalAction.NO_TRADE, _confidence(confidence), reasons, inputs, buy, sell, summary=summary
    )


def evaluate(table: FeatureTable, config: RuleConfig | None = None) -> Decision:
    """Decide for the newest candle in `table` (features from `compute_features`)."""
    cfg = config or RuleConfig()
    inputs = latest(table)
    previous = (
        latest({name: values[:-1] for name, values in table.items()})
        if len(table["close"]) > 1
        else {}
    )

    needed = ("ema_slow", "sma_slow", "rsi", "macd_hist", "atr_percent")
    if any(inputs.get(n) is None for n in needed):
        return _no_trade(
            [Reason("warming_up", "Not enough history yet for every indicator.", "info")],
            inputs,
            "Not enough data",
        )

    atr_percent = inputs["atr_percent"]
    assert atr_percent is not None
    if atr_percent > cfg.max_atr_percent or math.isinf(atr_percent):
        return _no_trade(
            [
                Reason(
                    "volatility_extreme",
                    f"Average candle range is {atr_percent:.1f}% of price: too volatile to trust.",
                    "info",
                )
            ],
            inputs,
            "Volatility too high",
        )

    votes = _vote_rules(inputs, previous, cfg)
    buy = sum(r.weight for r in votes if r.direction == "buy")
    sell = sum(r.weight for r in votes if r.direction == "sell")
    available = _available_weight(inputs)
    lead = max(buy, sell)
    confidence = lead / available if available else 0.0

    if buy >= cfg.conflict_score and sell >= cfg.conflict_score:
        reasons = [
            *votes,
            Reason("conflict", "Indicators disagree: strong signals on both sides.", "info"),
        ]
        return _no_trade(reasons, inputs, "Conflicting indicators", confidence, buy, sell)

    if buy >= cfg.act_score and sell < cfg.quiet_score:
        action, side = SignalAction.BUY, "buy"
    elif sell >= cfg.act_score and buy < cfg.quiet_score:
        action, side = SignalAction.SELL, "sell"
    else:
        reasons = [*votes, Reason("no_edge", "No side is decisive.", "neutral")]
        return Decision(
            SignalAction.HOLD,
            _confidence(confidence),
            reasons,
            inputs,
            buy,
            sell,
            summary="Nothing decisive",
        )

    if confidence < cfg.min_confidence:
        reasons = [
            *votes,
            Reason(
                "low_confidence",
                f"Agreement is only {confidence:.0%}; {cfg.min_confidence:.0%} is needed to act.",
                "info",
            ),
        ]
        return _no_trade(reasons, inputs, "Low confidence", confidence, buy, sell)

    return Decision(
        action,
        _confidence(confidence),
        votes,
        inputs,
        buy,
        sell,
        summary=f"{side.upper()}: {confidence:.0%} of the rule weight agrees",
    )
