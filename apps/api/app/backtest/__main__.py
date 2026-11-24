"""Command line: run a backtest on stored candles and store it.

    cd apps/api
    uv run python -m app.backtest run --symbol BTC/USDT --timeframe 1h
    uv run python -m app.backtest run --symbol BTC/USDT --timeframe 1h --judge-oos --yes
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
        if args.command == "research":
            from app.scalping.research import combos, run_research

            if args.judge_oos and not args.yes:
                print(  # noqa: T201
                    f"This spends the locked out-of-sample period of {len(combos())} "
                    "strategy/instrument/timeframe combinations, once each, with the declared "
                    "configuration (see app/scalping/research.py). Run again with --yes."
                )
                return 3
            try:
                results = await run_research(sessions, judge_oos=args.judge_oos)
            except OosLockedError as error:
                print(f"REFUSED: {error}")  # noqa: T201
                return 2
            for combo, runs in results.items():
                print(f"{combo.strategy} {combo.symbol} {combo.timeframe}: {len(runs)} runs")  # noqa: T201
            return 0
        if args.command == "research-report":
            from app.scalping.report import write_report

            print(await write_report(sessions))  # noqa: T201
            return 0
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
        if args.judge_oos and not args.yes:
            print(  # noqa: T201
                "This spends the locked out-of-sample period on THIS configuration, once.\n"
                f"  symbol {config.symbol}  timeframe {config.timeframe}\n"
                f"  config {config.config_hash()}  (settings plus the rules code)\n"
                f"  capital {config.capital}  fee {config.fee_pct}%  "
                f"slippage {config.slippage_bps} bps  latency {config.latency_candles}\n"
                "A different configuration (or changed rules) can never judge this period after "
                "this. Check the numbers, then run again with --yes."
            )
            return 3
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
    run.add_argument("--yes", action="store_true", help="confirm --judge-oos")
    research = sub.add_parser("research", help="the scalping research protocol (Phase 9b)")
    research.add_argument(
        "--judge-oos", action="store_true", help="spend the locked periods (once)"
    )
    research.add_argument("--yes", action="store_true", help="confirm --judge-oos")
    sub.add_parser("research-report", help="write docs/SCALPING_RESEARCH.md from stored runs")
    again = sub.add_parser("rerun")
    again.add_argument("run_id", type=int)
    raise SystemExit(asyncio.run(_main(parser.parse_args())))


if __name__ == "__main__":
    main()
