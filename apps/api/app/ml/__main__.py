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
    parser.add_subparsers(dest="command", required=True).add_parser("evaluate")
    parser.parse_args()
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
