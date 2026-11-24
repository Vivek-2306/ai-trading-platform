# ruff: noqa: RUF009  (Decimal defaults are immutable, so sharing them is safe)
"""An event-driven, long-only backtest that reuses the real rules and the real risk engine.

How a trade happens (and why there is no look-ahead):

1. After candle t has fully closed, the strategy sees only candles up to t and decides.
2. A BUY must pass the risk veto, exactly as a live signal does. It is filled at the OPEN of a
   later candle (t + 1 + latency), never at the close that produced the signal.
3. The trade is re-planned from the actual fill price (stop, target, size), still through the
   risk engine's `plan_long` and `position_size`. If the fill is unusable the trade is skipped.
4. While a position is open, each candle's low and high are checked: the stop first (a candle
   that touches both stop and target counts as a stop, the cautious assumption), then the
   target. A gap below the stop fills at the open; a target fills at the target price.
5. A SELL decision exits at the next candle's open. A position still open at the end of the
   data is closed at the last close and marked as such.

Costs: a fee on every fill's notional, and slippage against you on every market fill (entries,
stop and signal exits, the final close). Money is `Decimal`. Cash can never go negative (spot, no
leverage). The result depends only on the inputs: same candles and config, same trades.
"""

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from typing import Any

import numpy as np

from app.analysis.features import MIN_CANDLES, FeatureTable, compute_features
from app.analysis.indicators import CandleSeries
from app.backtest.identity import strategy_fingerprint
from app.data.adapters.base import RawCandle
from app.data.models import SignalAction
from app.risk.limits import RiskLimits
from app.risk.plan import Veto, plan_long
from app.risk.sizing import PositionSize, position_size, quantity_step
from app.risk.veto import PortfolioState, assess
from app.signals.rules import Decision, evaluate

D = Decimal
Strategy = Callable[[FeatureTable], Decision]


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    symbol: str
    timeframe: str
    strategy: str = "rules-v2"
    capital: Decimal = D("1000")
    fee_pct: Decimal = D("0.1")  # per fill, percent of notional (Binance spot default tier)
    slippage_bps: Decimal = D("5")  # per market fill, against you
    latency_candles: int = 0  # extra candles between the decision and the fill
    # The rest of the risk limits come from RiskLimits; only what changes results is recorded.
    risk_per_trade_pct: Decimal = D("0.5")
    max_capital_share_pct: Decimal = D("20")
    max_daily_loss_pct: Decimal = D("2")
    min_risk_reward: Decimal = D("1.5")
    stop_atr_multiple: Decimal = D("1.5")
    target_atr_multiple: Decimal = D("3")
    max_stop_distance_pct: Decimal = D("10")

    def __post_init__(self) -> None:
        if (
            self.capital <= 0
            or self.fee_pct < 0
            or self.slippage_bps < 0
            or self.latency_candles < 0
        ):
            raise ValueError(
                "capital must be positive; fees, slippage and latency cannot be negative"
            )

    def to_dict(self) -> dict[str, Any]:
        return {k: (str(v) if isinstance(v, Decimal) else v) for k, v in asdict(self).items()}

    def config_hash(self) -> str:
        """Identifies the configuration AND the code that interprets it (see identity.py)."""
        blob = json.dumps({**self.to_dict(), "code": strategy_fingerprint()}, sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()[:16]

    def risk_limits(self, capital: Decimal) -> RiskLimits:
        """The limits for one decision, sized from current equity."""
        return RiskLimits(
            _env_file=None,
            capital=capital,
            risk_per_trade_pct=self.risk_per_trade_pct,
            max_capital_share_pct=self.max_capital_share_pct,
            max_daily_loss_pct=self.max_daily_loss_pct,
            max_open_positions=1,
            min_risk_reward=self.min_risk_reward,
            stop_atr_multiple=self.stop_atr_multiple,
            target_atr_multiple=self.target_atr_multiple,
            max_stop_distance_pct=self.max_stop_distance_pct,
        )


@dataclass(frozen=True, slots=True)
class Trade:
    entry_ts: datetime
    exit_ts: datetime
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal
    pnl: Decimal  # net of fees and slippage
    fees: Decimal
    risk_amount: Decimal  # what the trade risked at entry (quantity x entry-to-stop)
    exit_reason: str  # "stop", "target", "signal" or "end_of_data"
    bars_held: int

    @property
    def r_multiple(self) -> Decimal:
        return self.pnl / self.risk_amount if self.risk_amount > 0 else D(0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_ts": self.entry_ts.isoformat(),
            "exit_ts": self.exit_ts.isoformat(),
            "entry_price": format(self.entry_price, "f"),
            "exit_price": format(self.exit_price, "f"),
            "quantity": format(self.quantity, "f"),
            "pnl": format(self.pnl, "f"),
            "fees": format(self.fees, "f"),
            "risk_amount": format(self.risk_amount, "f"),
            "r_multiple": format(self.r_multiple.quantize(D("0.01")), "f"),
            "exit_reason": self.exit_reason,
            "bars_held": self.bars_held,
        }


@dataclass(slots=True)
class BacktestResult:
    config: BacktestConfig
    times: list[datetime]
    equity: list[Decimal]  # mark-to-market at each candle's close
    trades: list[Trade]
    first_decision_index: int
    stats: dict[str, int] = field(default_factory=dict)  # signals, vetoes, skipped fills
    # What the strategy decided after each candle it was asked about: (candle index, action).
    decisions: list[tuple[int, str]] = field(default_factory=list)


@dataclass(slots=True)
class _Position:
    quantity: Decimal
    entry_price: Decimal
    entry_cost: Decimal  # fee paid on entry
    stop: Decimal
    target: Decimal
    risk_amount: Decimal
    entry_index: int
    entry_ts: datetime


@dataclass(slots=True)
class _Order:
    side: str  # "buy" or "sell"
    fill_index: int
    atr: float | None = None


def default_strategy(table: FeatureTable) -> Decision:
    return evaluate(table)


def _slip(price: Decimal, bps: Decimal, side: str) -> Decimal:
    factor = bps / 10_000
    return price * (1 + factor) if side == "buy" else price * (1 - factor)


def _fee(notional: Decimal, fee_pct: Decimal) -> Decimal:
    return notional * fee_pct / 100


def run_backtest(
    candles: list[RawCandle],
    config: BacktestConfig,
    strategy: Strategy = default_strategy,
    *,
    ask_at_last: bool = False,
) -> BacktestResult:
    """Replay `candles` (oldest first) through the strategy and the risk engine.

    `ask_at_last` also asks the strategy after the final candle (there is nothing to fill at, so
    nothing trades). The look-ahead check uses it to compare that last decision.
    """
    if len(candles) < MIN_CANDLES + 2:
        raise ValueError(f"need at least {MIN_CANDLES + 2} candles to backtest")
    ordered = sorted(candles, key=lambda c: c.ts)
    series = CandleSeries.from_candles(ordered)
    features = compute_features(series)  # causal: the value at t only uses candles up to t
    n = len(ordered)
    step = quantity_step(config.symbol)

    cash = config.capital
    position: _Position | None = None
    pending: _Order | None = None
    trades: list[Trade] = []
    equity: list[Decimal] = []
    stats = {"decisions": 0, "buy_signals": 0, "vetoed": 0, "skipped_fills": 0}
    decisions: list[tuple[int, str]] = []
    losses_by_day: dict[str, Decimal] = {}

    def close_position(index: int, price: Decimal, reason: str, market: bool) -> None:
        nonlocal cash, position
        assert position is not None
        fill = _slip(price, config.slippage_bps, "sell") if market else price
        proceeds = position.quantity * fill
        fee = _fee(proceeds, config.fee_pct)
        cash += proceeds - fee
        pnl = proceeds - fee - (position.quantity * position.entry_price + position.entry_cost)
        trades.append(
            Trade(
                entry_ts=position.entry_ts,
                exit_ts=ordered[index].ts,
                entry_price=position.entry_price,
                exit_price=fill,
                quantity=position.quantity,
                pnl=pnl,
                fees=position.entry_cost + fee,
                risk_amount=position.risk_amount,
                exit_reason=reason,
                bars_held=index - position.entry_index,
            )
        )
        if pnl < 0:
            day = ordered[index].ts.date().isoformat()
            losses_by_day[day] = losses_by_day.get(day, D(0)) - pnl
        position = None

    for i in range(n):
        candle = ordered[i]

        # 1. Orders scheduled for this candle fill at its open.
        if pending is not None and pending.fill_index == i:
            order, pending = pending, None
            if order.side == "buy" and position is None:
                fill = _slip(candle.open, config.slippage_bps, "buy")
                limits = config.risk_limits(max(cash, D("0.00000001")))
                plan = plan_long(
                    fill,
                    order.atr,
                    stop_atr_multiple=limits.stop_atr_multiple,
                    target_atr_multiple=limits.target_atr_multiple,
                    min_risk_reward=limits.min_risk_reward,
                    max_stop_distance_pct=limits.max_stop_distance_pct,
                )
                size = (
                    None
                    if isinstance(plan, Veto)
                    else position_size(
                        capital=cash,
                        risk_pct=limits.risk_per_trade_pct,
                        entry=plan.entry,
                        stop=plan.stop,
                        max_capital_share_pct=limits.max_capital_share_pct,
                        step=step,
                    )
                )
                if isinstance(plan, Veto) or size is None or isinstance(size, Veto):
                    stats["skipped_fills"] += 1
                else:
                    quantity = _affordable(size, fill, cash, config.fee_pct, step)
                    if quantity <= 0:
                        stats["skipped_fills"] += 1
                    else:
                        cost = quantity * fill
                        fee = _fee(cost, config.fee_pct)
                        cash -= cost + fee
                        position = _Position(
                            quantity=quantity,
                            entry_price=fill,
                            entry_cost=fee,
                            stop=plan.stop,
                            target=plan.target,
                            risk_amount=quantity * (fill - plan.stop),
                            entry_index=i,
                            entry_ts=candle.ts,
                        )
            elif order.side == "sell" and position is not None:
                close_position(i, candle.open, "signal", market=True)

        # 2. A position is exposed to this candle's range (the entry candle included).
        if position is not None:
            if candle.low <= position.stop:
                close_position(i, min(position.stop, candle.open), "stop", market=True)
            elif candle.high > position.target:  # must trade THROUGH the target to fill
                close_position(i, position.target, "target", market=False)

        # 3. Mark to market at the close.
        equity.append(cash + (position.quantity * candle.close if position else D(0)))

        # 4. After the close, the strategy decides from what it can see: candles up to i.
        if i < MIN_CANDLES or (i >= n - 1 and not ask_at_last) or pending is not None:
            continue
        view = {name: values[: i + 1] for name, values in features.items()}
        decision = strategy(view)
        stats["decisions"] += 1
        decisions.append((i, decision.action.value))
        fill_index = i + 1 + config.latency_candles
        if fill_index >= n:
            continue
        if position is None and decision.action is SignalAction.BUY:
            stats["buy_signals"] += 1
            day = candle.ts.date().isoformat()
            assessment = assess(
                decision,
                symbol=config.symbol,
                entry=candle.close,
                atr=decision.inputs.get("atr"),
                limits=config.risk_limits(max(cash, D("0.00000001"))),
                state=PortfolioState(0, losses_by_day.get(day, D(0))),
                kill_switch_on=False,
            )
            if assessment.action is SignalAction.BUY:
                pending = _Order("buy", fill_index, decision.inputs.get("atr"))
            else:
                stats["vetoed"] += 1
        elif position is not None and decision.action is SignalAction.SELL:
            pending = _Order("sell", fill_index)

    if position is not None:
        close_position(n - 1, ordered[-1].close, "end_of_data", market=True)
        equity[-1] = cash

    return BacktestResult(
        config=config,
        times=[c.ts for c in ordered],
        equity=equity,
        trades=trades,
        first_decision_index=MIN_CANDLES,
        stats=stats,
        decisions=decisions,
    )


def _affordable(
    size: PositionSize, fill: Decimal, cash: Decimal, fee_pct: Decimal, step: Decimal
) -> Decimal:
    """The sized quantity, cut down if cash cannot pay for it plus the fee (no leverage)."""
    quantity = size.quantity
    max_by_cash = cash / (fill * (1 + fee_pct / 100))
    if quantity > max_by_cash:
        quantity = (max_by_cash / step).to_integral_value(rounding=ROUND_DOWN) * step
    return quantity


def equity_array(result: BacktestResult) -> np.ndarray:
    return np.array([float(x) for x in result.equity], dtype=np.float64)
