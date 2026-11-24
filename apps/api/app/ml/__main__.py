"""Evaluate the model on the tuning region of stored candles:  python -m app.ml evaluate"""

import argparse
import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.analysis.indicators import CandleSeries
from app.backtest.runner import tuning_candles
from app.backtest.splits import OosKey
from app.core.config import get_settings
from app.data.models import AssetClass
from app.data.universe import InstrumentSpec
from app.ml.evaluate import evaluate_model
from app.ml.protocol import FOLD_ARGS, STRATEGY_NAME, SYMBOLS, TIMEFRAMES


async def _backtest(judge_oos: bool) -> int:
    from decimal import Decimal

    from app.backtest.engine import BacktestConfig
    from app.backtest.registry import register
    from app.backtest.runner import run_and_store
    from app.ml.protocol import ENTRY_THRESHOLD
    from app.ml.strategy import make_strategy

    engine = create_async_engine(get_settings().database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        for symbol in SYMBOLS:
            for timeframe in TIMEFRAMES:
                spec = InstrumentSpec("binance", symbol, AssetClass.CRYPTO)
                key = OosKey(symbol, timeframe, STRATEGY_NAME)
                context = CandleSeries.from_candles(await tuning_candles(sessions, spec, key))
                train_rows, test_rows = FOLD_ARGS[timeframe]
                register(make_strategy(context, train_rows, test_rows, ENTRY_THRESHOLD))
                config = BacktestConfig(
                    symbol,
                    timeframe,
                    strategy=STRATEGY_NAME,
                    capital=Decimal("1000"),
                    risk_per_trade_pct=Decimal("0.5"),
                    stop_atr_multiple=Decimal("1.0"),
                    target_atr_multiple=Decimal("1.6"),
                    min_risk_reward=Decimal("1.5"),
                    slippage_bps=Decimal("1"),
                )
                runs = await run_and_store(sessions, spec, config, judge_oos_period=judge_oos)
                for run in runs:
                    m = run.metrics
                    print(  # noqa: T201
                        f"{symbol} {timeframe} {run.segment}: trades={m.get('trades')} "
                        f"return={m.get('total_return_pct')}% pf={m.get('profit_factor')}"
                    )
    finally:
        await engine.dispose()
    return 0


async def _main() -> int:
    engine = create_async_engine(get_settings().database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        for symbol in SYMBOLS:
            for timeframe in TIMEFRAMES:
                spec = InstrumentSpec("binance", symbol, AssetClass.CRYPTO)
                candles = await tuning_candles(
                    sessions, spec, OosKey(symbol, timeframe, STRATEGY_NAME)
                )
                train_rows, test_rows = FOLD_ARGS[timeframe]
                ev, _ = evaluate_model(
                    CandleSeries.from_candles(candles),
                    min_train_rows=train_rows,
                    test_rows=test_rows,
                )
                print(  # noqa: T201
                    f"{symbol} {timeframe}: rows={ev.rows} base={ev.base_rate:.3f} "
                    f"auc={ev.auc and round(ev.auc, 3)} brier={ev.brier_model:.4f} "
                    f"prior={ev.brier_prior:.4f} coin={ev.brier_coin:.4f} "
                    f"ece={ev.ece_raw:.3f} breakeven={ev.breakeven:.3f} "
                    f"rules={ev.rules_buy} thr={ev.thresholds}"
                )
    finally:
        await engine.dispose()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.ml")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("evaluate")
    sub.add_parser(
        "backtest", help="tuning region and walk-forward only; the locked period stays shut"
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_backtest(False) if args.command == "backtest" else _main()))


if __name__ == "__main__":
    main()
