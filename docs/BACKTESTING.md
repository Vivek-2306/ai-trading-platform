# Backtesting

How the rules are measured. Nothing here places an order, and a backtest is not a promise: it
describes the past, with the costs and simplifications listed below.

## What a run does

`app/backtest/engine.py` replays stored candles through the same rule engine and the same risk
engine the live pipeline uses (ADR 0004).

- A decision after candle *t* sees only candles up to *t*. A BUY is filled at the **open of a
  later candle** (plus an optional latency delay), never at the close that produced it.
- Every BUY goes through the risk veto; the trade is re-planned from the actual fill price
  (stop, target, size). One position at a time, long-only, no leverage.
- Costs: a fee on every fill (default 0.1% per side) and slippage against you on market fills
  (default 5 bps). Stops are checked inside candles; a candle touching both stop and target
  counts as the stop; a gap below the stop fills at the open.
- A position still open at the end is closed at the last close.

## Honesty rules

- **Locked out-of-sample period.** The most recent fifth of history (fixed by its start time, so new
  data extends it) cannot be read by tuning or walk-forward code. The start is shared by every
  timeframe of a symbol (it is the same price history). Judging it is a one-time decision per
  configuration (`--judge-oos --yes`); a second, different configuration is refused by the code and by
  the database (`oos_locks`). Re-running the same configuration is allowed.
- **What "the same configuration" means.** The settings (fees, slippage, latency, capital, risk
  limits) **and the code that interprets them**: the rule engine, the indicators and features, the
  risk engine and the backtest engine itself are fingerprinted into the configuration hash
  (`app/backtest/identity.py`). Editing the rules and re-judging is a different configuration and is
  refused. The flip side: a refactor of those files also changes the hash, so a result can only be
  re-judged on identical code.
- **Before the first run.** At least 500 candles must be stored (the first run fixes where the locked
  period starts, so backfill first). The Celery task and the plain command line also create the lock;
  only `--judge-oos` spends it, and it checks the locked period has at least 100 candles first.
- **Walk-forward.** `rules-v2` has no fitted parameters, so walk-forward windows measure
  *consistency over time*, not parameter fit.
- **Leakage checks.** `find_backtest_lookahead` compares full and cut-off runs; a strategy that peeks
  is caught. It cannot see look-ahead inside the engine itself (such as a fill at the signal's own
  close): the hand-computed engine tests cover that. Results that look too good (profit factor above 5, Sharpe above 5, win rate above
  90% over 10+ trades) carry a warning.
- **Small samples.** Fewer than 30 trades carries a warning on every number.
- **Benchmark.** Tuning and out-of-sample runs are compared with buy-and-hold over the same period,
  same costs (walk-forward windows are summarised without a benchmark). Buy-and-hold is fully
  invested while the strategy risks a few percent per trade, so a smaller drawdown is reported with
  how little time the strategy was in the market, and a strategy that never traded is called out as
  staying out, not skill.

## Running

```bash
cd apps/api
uv run python -m app.backtest run --symbol BTC/USDT --timeframe 1h       # tuning + walk-forward
uv run python -m app.backtest run --symbol BTC/USDT --timeframe 1h --judge-oos   # once!
uv run python -m app.backtest rerun 12                                    # repeat a stored run
```

The Celery task `run_backtest` does the tuning and walk-forward runs only; it can never spend
the locked period. Results are stored append-only in `backtest_runs`; the web page `/backtests`
shows them.

## Definitions

A win is a trade with a profit; a loss has a loss; breakeven trades are counted separately. Sharpe
and time-in-market are measured from the first candle the strategy could decide on (not the
indicator warm-up). A target fills only when price trades through it; a candle that touches both
stop and target counts as the stop. The daily-loss limit is checked per UTC day of the decision
candle, summing losses only, against the current equity (conservative).

## Known simplifications

Flat fee and slippage percentages, no order-book depth or partial fills, candles assumed
contiguous (gaps are not modelled), a 24/7 calendar for the Sharpe annualisation (an
approximation for gold), one instrument at a time, and the daily-loss limit applied per UTC day.
