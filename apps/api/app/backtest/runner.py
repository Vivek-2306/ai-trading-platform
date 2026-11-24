"""Run backtests against stored candles and keep the results.

`run_and_store` makes the tuning run, the walk-forward windows and (when asked) the one allowed
judgement of the locked out-of-sample period, each with its buy-and-hold benchmark, and stores
every run append-only with everything needed to repeat it: the configuration, the candle range,
a fingerprint of the exact candles used and the code version.
"""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.analysis.features import MIN_CANDLES
from app.backtest.benchmark import compare, run_buy_and_hold
from app.backtest.engine import BacktestConfig, BacktestResult, run_backtest
from app.backtest.identity import strategy_fingerprint
from app.backtest.metrics import compute_metrics
from app.backtest.splits import MemoryRegistry, OosKey, OosLockedError, make_splits
from app.backtest.walkforward import oos_feed, run_on_tuning, walk_forward
from app.core.config import get_settings
from app.core.logging import get_logger
from app.data.adapters.base import RawCandle
from app.data.models import BacktestRun, Candle, Instrument
from app.data.universe import InstrumentSpec

logger = get_logger(__name__)

MAX_CURVE_POINTS = 400
MIN_HISTORY_TO_LOCK = 500  # candles needed before the locked period is fixed
MIN_OOS_CANDLES = 100  # a locked period smaller than this cannot be judged
_DECIMAL_FIELDS = {
    "capital",
    "fee_pct",
    "slippage_bps",
    "risk_per_trade_pct",
    "max_capital_share_pct",
    "max_daily_loss_pct",
    "min_risk_reward",
    "stop_atr_multiple",
    "target_atr_multiple",
    "max_stop_distance_pct",
}


def fingerprint(candles: list[RawCandle]) -> str:
    digest = hashlib.sha256()
    for c in candles:
        digest.update(
            f"{c.ts.isoformat()}|{c.open}|{c.high}|{c.low}|{c.close}|{c.volume}\n".encode()
        )
    return digest.hexdigest()


def code_version() -> str:
    return (get_settings().git_sha or "dev")[:40]


def config_from_dict(data: dict[str, Any]) -> BacktestConfig:
    values: dict[str, Any] = {k: Decimal(v) if k in _DECIMAL_FIELDS else v for k, v in data.items()}
    return BacktestConfig(**values)


def curves(strategy: BacktestResult, benchmark: BacktestResult) -> dict[str, Any]:
    """Equity curves for the chart, thinned to at most MAX_CURVE_POINTS points."""
    n = len(strategy.equity)
    stride = max(n // MAX_CURVE_POINTS, 1)
    picks = sorted({*range(0, n, stride), n - 1})
    return {
        "times": [strategy.times[i].isoformat() for i in picks],
        "strategy": [round(float(strategy.equity[i]), 2) for i in picks],
        "benchmark": [round(float(benchmark.equity[i]), 2) for i in picks],
    }


async def load_candles(
    session: AsyncSession, instrument_id: int, timeframe: str
) -> list[RawCandle]:
    rows = await session.execute(
        select(Candle)
        .where(Candle.instrument_id == instrument_id, Candle.timeframe == timeframe)
        .order_by(Candle.ts)
    )
    return [RawCandle(c.ts, c.open, c.high, c.low, c.close, c.volume) for c in rows.scalars()]


async def _registry(session: AsyncSession, key: OosKey) -> MemoryRegistry:
    """An in-memory registry filled from the database lock (the splits code is synchronous)."""
    registry = MemoryRegistry()
    row = (
        await session.execute(
            text(
                "SELECT oos_start, config_hash FROM oos_locks "
                "WHERE symbol = :s AND timeframe = :t AND strategy = :g"
            ),
            {"s": key.symbol, "t": key.timeframe, "g": key.strategy},
        )
    ).one_or_none()
    if row is not None:
        registry.set_start(key, row.oos_start)
        if row.config_hash:
            registry.set_judged(key, row.config_hash)
        return registry
    # A new timeframe for a symbol that already has a locked period: it is the same price
    # history, so it shares that start (otherwise tuning on 1d could use what 1h judged).
    other = (
        await session.execute(
            text(
                "SELECT oos_start FROM oos_locks WHERE symbol = :s AND strategy = :g "
                "ORDER BY created_at LIMIT 1"
            ),
            {"s": key.symbol, "g": key.strategy},
        )
    ).scalar_one_or_none()
    if other is not None:
        registry.set_start(key, other)
    return registry


async def _lock_saved(session: AsyncSession, key: OosKey) -> bool:
    row = await session.execute(
        text("SELECT 1 FROM oos_locks WHERE symbol = :s AND timeframe = :t AND strategy = :g"),
        {"s": key.symbol, "t": key.timeframe, "g": key.strategy},
    )
    return row.first() is not None


async def _save_lock(session: AsyncSession, key: OosKey, oos_start: datetime) -> None:
    await session.execute(
        text(
            "INSERT INTO oos_locks (symbol, timeframe, strategy, oos_start) "
            "VALUES (:s, :t, :g, :o) ON CONFLICT DO NOTHING"
        ),
        {"s": key.symbol, "t": key.timeframe, "g": key.strategy, "o": oos_start},
    )
    await session.commit()


async def _claim_judgement(session: AsyncSession, key: OosKey, config_hash: str) -> None:
    """Record, atomically, that this configuration judged the locked period. If another
    configuration got there first, refuse (and nothing is stored)."""
    result = await session.execute(
        text(
            "UPDATE oos_locks SET config_hash = :h WHERE symbol = :s AND timeframe = :t "
            "AND strategy = :g AND config_hash IS NULL"
        ),
        {"h": config_hash, "s": key.symbol, "t": key.timeframe, "g": key.strategy},
    )
    await session.commit()
    stored = (
        await session.execute(
            text(
                "SELECT config_hash FROM oos_locks "
                "WHERE symbol = :s AND timeframe = :t AND strategy = :g"
            ),
            {"s": key.symbol, "t": key.timeframe, "g": key.strategy},
        )
    ).scalar_one()
    if stored != config_hash:
        raise OosLockedError(
            f"The out-of-sample period for {key.symbol} {key.timeframe} was already used to "
            f"judge configuration {stored}; {config_hash} cannot judge it too."
        )
    _ = result


@dataclass(frozen=True, slots=True)
class StoredRun:
    id: int
    segment: str
    metrics: dict[str, Any]


def _row(
    instrument_id: int,
    config: BacktestConfig,
    segment: str,
    feed: list[RawCandle],
    strategy: BacktestResult | None,
    benchmark_result: BacktestResult | None,
    details: dict[str, Any],
    *,
    metrics_override: dict[str, Any] | None = None,
) -> BacktestRun:
    comparison = compare(strategy, benchmark_result) if strategy and benchmark_result else None
    metrics = (
        metrics_override
        if metrics_override is not None
        else compute_metrics(strategy).to_dict()
        if strategy
        else {}
    )
    return BacktestRun(
        instrument_id=instrument_id,
        timeframe=config.timeframe,
        strategy=config.strategy,
        segment=segment,
        config=config.to_dict(),
        config_hash=config.config_hash(),
        range_start=feed[0].ts,
        range_end=feed[-1].ts,
        candle_count=len(feed),
        data_fingerprint=fingerprint(feed),
        code_version=code_version(),
        metrics=metrics,
        benchmark=comparison.to_dict() if comparison else {},
        trades=[t.to_dict() for t in strategy.trades] if strategy else [],
        equity=curves(strategy, benchmark_result) if strategy and benchmark_result else {},
        details=details,
    )


def _window_summary(results: list[Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = []
    for w in results:
        m = compute_metrics(w.result)
        rows.append(
            {
                "start": w.result.times[0].isoformat(),
                "end": w.result.times[-1].isoformat(),
                "trades": m.trades,
                "return_pct": round(m.total_return_pct, 4),
                "max_drawdown_pct": round(m.max_drawdown_pct, 4),
                "net_pnl": format(m.net_pnl, "f"),
            }
        )
    returns = [r["return_pct"] for r in rows]
    summary = {
        "windows": len(rows),
        "profitable_windows": sum(1 for r in returns if r > 0),
        "mean_window_return_pct": round(sum(returns) / len(returns), 4) if returns else None,
        "best_window_return_pct": max(returns) if returns else None,
        "worst_window_return_pct": min(returns) if returns else None,
        "total_trades": sum(r["trades"] for r in rows),
        "warnings": (
            ["Walk-forward windows with few trades each: read the consistency, not the totals."]
            if rows
            else ["Not enough history for a single walk-forward window."]
        ),
    }
    return summary, rows


async def run_and_store(
    sessions: async_sessionmaker[AsyncSession],
    spec: InstrumentSpec,
    config: BacktestConfig,
    *,
    walk_forward_run: bool = True,
    judge_oos_period: bool = False,
    oos_fraction: float = 0.2,
) -> list[StoredRun]:
    """Tuning run, walk-forward and optionally the one judgement of the locked period."""
    key = OosKey(config.symbol, config.timeframe, config.strategy)
    stored: list[StoredRun] = []
    async with sessions() as session:
        instrument = (
            await session.execute(
                select(Instrument).where(
                    Instrument.venue == spec.venue, Instrument.symbol == spec.symbol
                )
            )
        ).scalar_one()
        candles = await load_candles(session, instrument.id, config.timeframe)
        registry = await _registry(session, key)
        if len(candles) < MIN_HISTORY_TO_LOCK:
            raise ValueError(
                f"only {len(candles)} candles are stored; backfill at least {MIN_HISTORY_TO_LOCK} "
                "before backtesting (the first run fixes where the locked period starts)"
            )
        existed = registry.get(key) is not None
        splits = make_splits(candles, key, registry, oos_fraction=oos_fraction)
        if not existed or not await _lock_saved(session, key):
            await _save_lock(session, key, splits.oos.oos_start)
            # Another run may have created the lock first: always use what the database holds.
            registry = await _registry(session, key)
            splits = make_splits(candles, key, registry, oos_fraction=oos_fraction)

        runs: list[BacktestRun] = []
        tuning = run_on_tuning(splits, config)
        runs.append(
            _row(
                instrument.id,
                config,
                "tuning",
                splits.tuning,
                tuning,
                run_buy_and_hold(splits.tuning, config),
                {"stats": tuning.stats, "oos_start": splits.oos.oos_start.isoformat()},
            )
        )
        if walk_forward_run:
            size = len(splits.tuning)
            train, test = max(size // 2, 100), max(size // 8, 60)
            windows = walk_forward(splits, config, train_size=train, test_size=test)
            summary, rows = _window_summary(windows)
            runs.append(
                _row(
                    instrument.id,
                    config,
                    "walk_forward",
                    splits.tuning,
                    None,
                    None,
                    {"train_size": train, "test_size": test, "windows": rows},
                    metrics_override=summary,
                )
            )
        if judge_oos_period:
            feed = oos_feed(splits, config)  # raises OosLockedError if another config judged it
            if len(feed) - MIN_CANDLES < MIN_OOS_CANDLES:
                raise ValueError(
                    f"the locked period has only {len(feed) - MIN_CANDLES} candles; at least "
                    f"{MIN_OOS_CANDLES} are needed, so it is not spent. Wait for more data."
                )
            verdict = run_backtest(feed, config)  # if this fails, the lock is not spent
            await _claim_judgement(session, key, config.config_hash())
            runs.append(
                _row(
                    instrument.id,
                    config,
                    "oos",
                    feed,
                    verdict,
                    run_buy_and_hold(feed, config),
                    {
                        "stats": verdict.stats,
                        "oos_start": splits.oos.oos_start.isoformat(),
                        "note": "Judged once; this period can no longer be used to tune.",
                        "strategy_fingerprint": strategy_fingerprint(),
                    },
                )
            )
        session.add_all(runs)
        await session.commit()
        stored = [StoredRun(r.id, r.segment, r.metrics) for r in runs]
    logger.info(
        "backtest_stored", symbol=config.symbol, timeframe=config.timeframe, runs=len(stored)
    )
    return stored


@dataclass(frozen=True, slots=True)
class RerunResult:
    identical: bool
    reasons: list[str]


async def rerun(sessions: async_sessionmaker[AsyncSession], run_id: int) -> RerunResult:
    """Run a stored tuning or out-of-sample run again from its config and candle range, and say
    whether the data and the results are the same."""
    async with sessions() as session:
        run = await session.get(BacktestRun, run_id)
        if run is None:
            raise LookupError(f"no backtest run {run_id}")
        if run.segment not in ("tuning", "oos"):
            raise ValueError("only tuning and out-of-sample runs can be re-run directly")
        candles = await load_candles(session, run.instrument_id, run.timeframe)
    feed = [c for c in candles if run.range_start <= c.ts <= run.range_end]
    config = config_from_dict(run.config)
    reasons: list[str] = []
    if fingerprint(feed) != run.data_fingerprint:
        reasons.append("the stored candles in that range have changed since the run")
    result = run_backtest(feed, config)
    if [t.to_dict() for t in result.trades] != run.trades:
        reasons.append("the trades differ")
    if compute_metrics(result).to_dict() != run.metrics:
        reasons.append("the metrics differ")
    return RerunResult(not reasons, reasons)


def utc_now() -> datetime:
    return datetime.now(UTC)
