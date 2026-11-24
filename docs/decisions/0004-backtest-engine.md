# ADR 0004: A custom event-driven backtest engine, not vectorbt

- Status: Accepted
- Date: 2026-11-24

## Context

Phase 9 must measure the rules honestly. The plan named vectorbt. vectorbt is built for
vectorised, signal-array backtests. Our strategy is different in ways that matter:

- The decision at each candle is the real rule engine (`rules-v2`), which produces BUY, SELL,
  HOLD or NO TRADE with reasons.
- Every BUY must pass the real risk engine, with a stop and target from the ATR at the time,
  a position size from current equity, a daily-loss limit and one position at a time.
- Fills must happen at a later candle's open, with fees, slippage and a latency delay, and stops
  are checked inside candles (stop before target when both are touched).

Reproducing that in vectorbt means re-implementing the risk engine in array form, and then the
backtest would test a copy, not the code that runs live.

## Decision

Write a small event-driven engine (`app/backtest/engine.py`) that calls the same `evaluate`,
`assess`, `plan_long` and `position_size` the live pipeline uses. Money is `Decimal`. It is
deterministic. vectorbt stays installed for later research (parameter sweeps, ML labels), but
is not used to judge strategies.

## Consequences

- A backtest and live signals share their decision code, so they cannot drift apart.
- Slower than vectorised code (about a second for 26,000 hourly candles), which is fine here.
- We own the correctness of fills and costs, so they are tested against hand-computed scenarios,
  and leakage is checked explicitly (Phase 9 tickets 69 and 72).
- Known simplifications: one position at a time per instrument, long-only, no partial fills, no
  order-book depth, candles assumed contiguous (gaps are not modelled), fees and slippage are
  flat percentages.
