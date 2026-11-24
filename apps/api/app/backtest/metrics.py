"""Backtest metrics: what a run did, with the caveats attached.

Every number here describes the past. With few trades they are mostly noise, so a result
carries a warning when the sample is too small to mean anything (`MIN_MEANINGFUL_TRADES`).
Sharpe is computed from the equity curve's per-candle returns with a zero risk-free rate and
scaled by the square root of candles per year (24/7 crypto calendar: an approximation for gold).
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import numpy as np

from app.backtest.engine import BacktestResult

MIN_MEANINGFUL_TRADES = 30

PERIODS_PER_YEAR = {"1m": 525_600.0, "5m": 105_120.0, "1h": 8_760.0, "1d": 365.0}


@dataclass(frozen=True, slots=True)
class Metrics:
    trades: int
    wins: int
    losses: int
    breakeven: int
    win_rate_pct: float | None
    profit_factor: float | None  # gross profit / gross loss; None when there were no losses
    expectancy: Decimal | None  # average net P&L per trade, in the quote currency
    expectancy_r: float | None  # average net P&L per trade in units of what it risked
    avg_win: Decimal | None
    avg_loss: Decimal | None
    payoff_ratio: float | None  # average win / average loss size
    total_return_pct: float
    max_drawdown_pct: float
    sharpe: float | None
    exposure_pct: float  # share of candles with a position open
    fees_paid: Decimal
    gross_pnl: Decimal  # P&L before fees (slippage is inside prices)
    net_pnl: Decimal
    longest_losing_streak: int
    avg_bars_held: float | None
    initial_equity: Decimal
    final_equity: Decimal
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        def fmt(value: object) -> object:
            if isinstance(value, Decimal):
                return format(value, "f")
            if isinstance(value, float):
                return None if not np.isfinite(value) else round(value, 6)
            return value

        return {name: fmt(getattr(self, name)) for name in self.__slots__}


def max_drawdown_pct(equity: np.ndarray) -> float:
    """Largest peak-to-trough fall of the equity curve, as a percent of the peak."""
    if len(equity) == 0:
        return 0.0
    peaks = np.maximum.accumulate(equity)
    with np.errstate(divide="ignore", invalid="ignore"):
        falls = np.where(peaks > 0, (peaks - equity) / peaks, 0.0)
    return float(falls.max() * 100.0)


def sharpe_ratio(equity: np.ndarray, periods_per_year: float) -> float | None:
    """Mean over standard deviation of per-candle returns, annualised. None if it has no spread."""
    if len(equity) < 3:
        return None
    previous = equity[:-1]
    with np.errstate(divide="ignore", invalid="ignore"):
        returns = np.where(previous > 0, equity[1:] / previous - 1.0, 0.0)
    spread = float(np.std(returns, ddof=1))
    if spread == 0.0 or not np.isfinite(spread):
        return None
    return float(np.mean(returns) / spread * np.sqrt(periods_per_year))


def compute_metrics(result: BacktestResult) -> Metrics:
    trades = result.trades
    pnls = [t.pnl for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    breakeven = len(pnls) - len(wins) - len(losses)
    gross_win = sum(wins, Decimal(0))
    gross_loss = -sum((p for p in pnls if p < 0), Decimal(0))
    # Before the first decision the strategy cannot act (indicator warm-up): those flat candles
    # would dilute Sharpe and exposure, so measure from the first decision on.
    live = result.equity[result.first_decision_index :] or result.equity
    equity = np.array([float(x) for x in live], dtype=np.float64)
    initial, final = live[0], live[-1]
    fees = sum((t.fees for t in trades), Decimal(0))
    net = sum(pnls, Decimal(0))
    n = len(trades)

    streak = longest = 0
    for p in pnls:
        streak = streak + 1 if p < 0 else 0
        longest = max(longest, streak)

    avg_win = gross_win / len(wins) if wins else None
    avg_loss = (-gross_loss / len([p for p in pnls if p < 0])) if gross_loss > 0 else None
    exposure = sum(t.bars_held + 1 for t in trades) / max(len(live), 1) * 100.0  # entry bar counts

    warnings: list[str] = []
    if n == 0:
        warnings.append("No trades: there is nothing to measure.")
    elif n < MIN_MEANINGFUL_TRADES:
        warnings.append(
            f"Only {n} trades: fewer than {MIN_MEANINGFUL_TRADES}, so win rate, profit factor "
            "and the rest are mostly noise."
        )

    periods = PERIODS_PER_YEAR[result.config.timeframe]
    profit_factor = float(gross_win / gross_loss) if gross_loss > 0 else None
    sharpe = sharpe_ratio(equity, periods)
    win_rate = len(wins) / n * 100.0 if n else None
    if n >= 10 and (
        (profit_factor is not None and profit_factor > 5)
        or (sharpe is not None and sharpe > 5)
        or (win_rate is not None and win_rate > 90)
    ):
        warnings.append(
            "Too good to be true: results this strong in a backtest usually mean look-ahead, "
            "a bug, or luck. Run the leakage check before believing them."
        )
    return Metrics(
        trades=n,
        wins=len(wins),
        losses=len(losses),
        breakeven=breakeven,
        win_rate_pct=win_rate,
        profit_factor=profit_factor,
        expectancy=net / n if n else None,
        expectancy_r=(
            float(sum((t.r_multiple for t in trades if t.risk_amount > 0), Decimal(0)) / n)
            if n
            else None
        ),
        avg_win=avg_win,
        avg_loss=avg_loss,
        payoff_ratio=float(avg_win / -avg_loss) if avg_win and avg_loss else None,
        total_return_pct=float((final - initial) / initial * 100) if initial else 0.0,
        max_drawdown_pct=max_drawdown_pct(equity),
        sharpe=sharpe,
        exposure_pct=exposure,
        fees_paid=fees,
        gross_pnl=net + fees,
        net_pnl=net,
        longest_losing_streak=longest,
        avg_bars_held=sum(t.bars_held for t in trades) / n if n else None,
        initial_equity=initial,
        final_equity=final,
        warnings=warnings,
    )
