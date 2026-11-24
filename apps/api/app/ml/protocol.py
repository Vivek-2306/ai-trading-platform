"""The ML research protocol, declared BEFORE any model result was seen.

Instruments BTC/USDT and ETH/USDT on 1h and 1d. The model is LightGBM with the parameters in
`train.PARAMS` (not tuned). Walk-forward folds: 1h trains on at least 3000 rows and tests blocks
of 1000; 1d (only about 1750 rows in the tuning region) trains on at least 500 and tests blocks
of 200. Entry rule for the backtest (AITP-84): the model's probability must be at least
`ENTRY_THRESHOLD`. The threshold is set from the break-even win rate (about 38% before costs,
and higher after them) plus a margin, not from looking at which value backtests best.
"""

STRATEGY_NAME = "ml-lgbm-v1"
SYMBOLS = ("BTC/USDT", "ETH/USDT")
TIMEFRAMES = ("1h", "1d")
FOLD_ARGS: dict[str, tuple[int, int]] = {  # (min_train_rows, test_rows)
    "1h": (3000, 1000),
    "1d": (500, 200),
}
ENTRY_THRESHOLD = 0.50
