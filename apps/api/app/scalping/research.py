"""The scalping research protocol, declared BEFORE the out-of-sample period is judged.

Strategies: scalp-ema-cross, scalp-vwap-pullback, scalp-breakout (parameters fixed in
strategies.py). Instruments: BTC/USDT and ETH/USDT. Timeframes: 1m (88 days, the most the 90-day
retention keeps) and 5m (about 2 years). Both share one locked period per instrument and
strategy: the last fifth of the 1m history, about 18 days.

Judged configuration: the regular Binance tier (0.10% maker and taker), 1 bp slippage, stop
1.0 ATR, target 1.6 ATR, 0.5% of capital per trade, at most 20 trades a day, a pause after 3
losses in a row. Two things were corrected after the first dry run on the TUNING region (the
locked period was untouched, and both are setup facts rather than tuning for profit):

- Target 1.6 ATR instead of 1.5: rounding the stop and target cautiously left the risk-to-reward
  just under the 1.5 minimum, so the risk engine vetoed every entry.
- Slippage 1 bp instead of 5 bps: 5 bps is a swing-trading default and is unrealistically harsh
  for small market orders on BTC and ETH (the spread there is a fraction of a bp), and at 1m it
  was larger than the average candle range, which decided every result. The first dry run's
  5 bp results remain stored, labelled by their configuration.

Per strategy, instrument and timeframe: a tuning run and walk-forward windows (the tuning region
only) and ONE judgement of the locked period with the declared configuration. Cheaper cost tiers
are run on the tuning region only, to show whether costs alone are the problem; they are
information, not a way to pick a configuration after the fact.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.backtest.costs import tier
from app.backtest.engine import BacktestConfig
from app.backtest.runner import StoredRun, run_and_store
from app.data.models import AssetClass
from app.data.universe import InstrumentSpec

STRATEGIES = ("scalp-ema-cross", "scalp-vwap-pullback", "scalp-breakout")
SYMBOLS = ("BTC/USDT", "ETH/USDT")
TIMEFRAMES = (
    "1m",
    "5m",
)  # 1m first: its short history decides where the shared locked period starts
JUDGED_TIER = "binance_regular"
SENSITIVITY_TIERS = ("binance_bnb", "optimistic_bound")
SLIPPAGE_BPS = Decimal("1")


def config_for(symbol: str, timeframe: str, strategy: str, tier_name: str) -> BacktestConfig:
    t = tier(tier_name)
    return BacktestConfig(
        symbol=symbol,
        timeframe=timeframe,
        strategy=strategy,
        capital=Decimal("1000"),
        fee_pct=t.taker_pct,
        maker_fee_pct=t.maker_pct,
        slippage_bps=SLIPPAGE_BPS,
        risk_per_trade_pct=Decimal("0.5"),
        stop_atr_multiple=Decimal("1.0"),
        target_atr_multiple=Decimal("1.6"),
        min_risk_reward=Decimal("1.5"),
        max_trades_per_day=20,
        cooldown_after_losses=3,
        cooldown_minutes=60,
    )


@dataclass(frozen=True, slots=True)
class Combo:
    strategy: str
    symbol: str
    timeframe: str


def combos() -> list[Combo]:
    return [Combo(s, sym, tf) for s in STRATEGIES for sym in SYMBOLS for tf in TIMEFRAMES]


def spec_for(symbol: str) -> InstrumentSpec:
    return InstrumentSpec("binance", symbol, AssetClass.CRYPTO)


async def run_research(
    sessions: async_sessionmaker[AsyncSession], *, judge_oos: bool
) -> dict[Combo, list[StoredRun]]:
    """Run the whole protocol. `judge_oos` spends the locked periods (once per combination)."""
    out: dict[Combo, list[StoredRun]] = {}
    for combo in combos():
        spec = spec_for(combo.symbol)
        main = config_for(combo.symbol, combo.timeframe, combo.strategy, JUDGED_TIER)
        runs = await run_and_store(sessions, spec, main, judge_oos_period=judge_oos)
        for name in SENSITIVITY_TIERS:
            variant = config_for(combo.symbol, combo.timeframe, combo.strategy, name)
            runs += await run_and_store(sessions, spec, variant, walk_forward_run=False)
        out[combo] = runs
    return out
