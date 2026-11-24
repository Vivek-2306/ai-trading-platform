"""Buy-and-hold: the bar any strategy has to clear.

Same candles, same period, same fees and slippage as the strategy run, so the comparison is net
of costs on both sides. It buys with all the capital at the first candle the strategy could have
traded at and holds to the end. A strategy that cannot beat this, after costs, is not worth its
complexity (though a smaller drawdown can still be worth something, and the report says so).
"""

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from typing import Any

from app.analysis.features import MIN_CANDLES
from app.backtest.engine import BacktestConfig, BacktestResult, Trade
from app.backtest.metrics import Metrics, compute_metrics
from app.data.adapters.base import RawCandle
from app.risk.sizing import quantity_step

D = Decimal


def run_buy_and_hold(candles: list[RawCandle], config: BacktestConfig) -> BacktestResult:
    ordered = sorted(candles, key=lambda c: c.ts)
    n = len(ordered)
    if n < MIN_CANDLES + 2:
        raise ValueError(f"need at least {MIN_CANDLES + 2} candles")
    entry_index = MIN_CANDLES + 1  # the earliest candle the strategy could have filled at
    slip = config.slippage_bps / 10_000
    fee_rate = config.fee_pct / 100
    fill = ordered[entry_index].open * (1 + slip)
    step = quantity_step(config.symbol)
    quantity = (config.capital / (fill * (1 + fee_rate)) / step).to_integral_value(
        rounding=ROUND_DOWN
    ) * step
    entry_fee = quantity * fill * fee_rate
    cash = config.capital - quantity * fill - entry_fee

    equity = [config.capital] * entry_index + [
        cash + quantity * ordered[i].close for i in range(entry_index, n)
    ]
    exit_fill = ordered[-1].close * (1 - slip)
    proceeds = quantity * exit_fill
    exit_fee = proceeds * fee_rate
    equity[-1] = cash + proceeds - exit_fee  # the final value after selling, like the strategy
    pnl = proceeds - exit_fee - quantity * fill - entry_fee
    trade = Trade(
        entry_ts=ordered[entry_index].ts,
        exit_ts=ordered[-1].ts,
        entry_price=fill,
        exit_price=exit_fill,
        quantity=quantity,
        pnl=pnl,
        fees=entry_fee + exit_fee,
        risk_amount=quantity * fill,  # buy-and-hold has no stop: the whole position is at risk
        exit_reason="end_of_data",
        bars_held=n - 1 - entry_index,
    )
    return BacktestResult(
        config=config,
        times=[c.ts for c in ordered],
        equity=equity,
        trades=[trade],
        first_decision_index=MIN_CANDLES,
        stats={"decisions": 0, "buy_signals": 1, "vetoed": 0, "skipped_fills": 0},
    )


@dataclass(frozen=True, slots=True)
class Comparison:
    strategy: Metrics
    benchmark: Metrics
    excess_return_pct: float
    beat_on_return: bool
    beat_on_drawdown: bool  # a smaller worst fall
    beat_on_sharpe: bool | None
    verdict: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_return_pct": round(self.strategy.total_return_pct, 4),
            "benchmark_return_pct": round(self.benchmark.total_return_pct, 4),
            "excess_return_pct": round(self.excess_return_pct, 4),
            "strategy_max_drawdown_pct": round(self.strategy.max_drawdown_pct, 4),
            "benchmark_max_drawdown_pct": round(self.benchmark.max_drawdown_pct, 4),
            "strategy_sharpe": self.strategy.sharpe,
            "benchmark_sharpe": self.benchmark.sharpe,
            "beat_on_return": self.beat_on_return,
            "beat_on_drawdown": self.beat_on_drawdown,
            "beat_on_sharpe": self.beat_on_sharpe,
            "verdict": self.verdict,
            "benchmark": self.benchmark.to_dict(),
        }


def compare(strategy: BacktestResult, benchmark: BacktestResult) -> Comparison:
    s, b = compute_metrics(strategy), compute_metrics(benchmark)
    excess = s.total_return_pct - b.total_return_pct
    beat_return = excess > 0
    smaller_drawdown = s.max_drawdown_pct < b.max_drawdown_pct
    beat_sharpe = None if s.sharpe is None or b.sharpe is None else s.sharpe > b.sharpe
    if beat_return:
        verdict = (
            f"Beat buy-and-hold by {excess:.2f} percentage points after costs "
            f"({s.total_return_pct:.2f}% vs {b.total_return_pct:.2f}%)."
        )
    elif smaller_drawdown:
        verdict = (
            f"Lagged buy-and-hold by {-excess:.2f} points ({s.total_return_pct:.2f}% vs "
            f"{b.total_return_pct:.2f}%) but with a smaller worst fall "
            f"({s.max_drawdown_pct:.1f}% vs {b.max_drawdown_pct:.1f}%)."
        )
    else:
        verdict = (
            f"Did not beat buy-and-hold: {s.total_return_pct:.2f}% vs {b.total_return_pct:.2f}%, "
            f"with no smaller drawdown."
        )
    if s.warnings:
        verdict += " " + s.warnings[0]
    return Comparison(s, b, excess, beat_return, smaller_drawdown, beat_sharpe, verdict)
