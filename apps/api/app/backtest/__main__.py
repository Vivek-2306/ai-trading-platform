"""Command line: run a backtest on stored candles and store it.

    cd apps/api
    uv run python -m app.backtest run --symbol BTC/USDT --timeframe 1h
    uv run python -m app.backtest run --symbol BTC/USDT --timeframe 1h --judge-oos
    uv run python -m app.backtest rerun 12

`--judge-oos` spends the locked out-of-sample period on this configuration. It can be done once
per configuration, and a second, different configuration is refused. Read docs/BACKTESTING.md
first.
"""

import argparse
import asyncio
from decimal import Decimal

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.backtest.engine import BacktestConfig
from app.backtest.runner import rerun, run_and_store
from app.backtest.splits import OosLockedError
from app.core.config import get_settings
from app.data.models import AssetClass
from app.data.universe import InstrumentSpec


def _spec(symbol: str) -> InstrumentSpec:
    gold = symbol.startswith("PAXG")
    return InstrumentSpec("binance", symbol, AssetClass.GOLD if gold else AssetClass.CRYPTO)


async def _main(args: argparse.Namespace) -> int:
    engine = create_async_engine(get_settings().database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        if args.command == "rerun":
            result = await rerun(sessions, args.run_id)
            print("identical" if result.identical else "DIFFERENT: " + "; ".join(result.reasons))  # noqa: T201
            return 0 if result.identical else 1
        config = BacktestConfig(
            symbol=args.symbol,
            timeframe=args.timeframe,
            capital=Decimal(args.capital),
            fee_pct=Decimal(args.fee_pct),
            slippage_bps=Decimal(args.slippage_bps),
            latency_candles=args.latency,
        )
        try:
            runs = await run_and_store(
                sessions, _spec(args.symbol), config, judge_oos_period=args.judge_oos
            )
        except OosLockedError as error:
            print(f"REFUSED: {error}")  # noqa: T201
            return 2
        for run in runs:
            m = run.metrics
            print(  # noqa: T201
                f"run {run.id} [{run.segment}] trades={m.get('trades', m.get('total_trades'))} "
                f"return={m.get('total_return_pct', m.get('mean_window_return_pct'))}%"
            )
        return 0
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run or repeat a backtest.")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--symbol", required=True)
    run.add_argument("--timeframe", required=True, choices=["1m", "5m", "1h", "1d"])
    run.add_argument("--capital", default="1000")
    run.add_argument("--fee-pct", default="0.1")
    run.add_argument("--slippage-bps", default="5")
    run.add_argument("--latency", type=int, default=0)
    run.add_argument("--judge-oos", action="store_true", help="spend the locked period (once)")
    again = sub.add_parser("rerun")
    again.add_argument("run_id", type=int)
    raise SystemExit(asyncio.run(_main(parser.parse_args())))


if __name__ == "__main__":
    main()
