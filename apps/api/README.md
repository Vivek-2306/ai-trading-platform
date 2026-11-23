# apps/api

Python backend for the AI Trading Platform: FastAPI app, background workers and the
analysis, signal, risk, execution and backtest engines.

```bash
uv sync                 # install into .venv
```

Module layout:

| Module | Purpose |
| --- | --- |
| `app/api` | HTTP routes and dependencies |
| `app/core` | Settings, logging, shared utilities |
| `app/data` | Market data, news and storage access |
| `app/analysis` | Indicators, patterns, fundamentals, sentiment |
| `app/signals` | Ensemble that turns analysis into Buy/Sell/Hold/NO TRADE |
| `app/risk` | Stop-loss, targets, position sizing, limits (can veto any signal) |
| `app/execution` | Paper and broker order execution |
| `app/backtest` | Backtesting and performance tracking |
