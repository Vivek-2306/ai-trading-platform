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
  data extends it) cannot be read by tuning or walk-forward code. Judging it is a one-time
  decision per configuration (`--judge-oos`); a second, different configuration is refused by the
  code and by the database (`oos_locks`). Re-running the same configuration is allowed.
- **Walk-forward.** `rules-v2` has no fitted parameters, so walk-forward windows measure
  *consistency over time*, not parameter fit.
- **Leakage checks.** `find_backtest_lookahead` compares full and cut-off runs; a strategy that peeks
  is caught. Results that look too good (profit factor above 5, Sharpe above 5, win rate above
  90% over 10+ trades) carry a warning.
- **Small samples.** Fewer than 30 trades carries a warning on every number.
- **Benchmark.** Every run is compared with buy-and-hold over the same period, same costs.

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

## Known simplifications

Flat fee and slippage percentages, no order-book depth or partial fills, candles assumed
contiguous (gaps are not modelled), a 24/7 calendar for the Sharpe annualisation (an
approximation for gold), one instrument at a time, and the daily-loss limit applied per UTC day.
