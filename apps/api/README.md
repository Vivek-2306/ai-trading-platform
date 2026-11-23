# apps/api

Python backend for the AI Trading Platform: FastAPI app, background workers and the
analysis, signal, risk, execution and backtest engines.

```bash
uv sync                                                   # install into .venv
uv run uvicorn app.main:create_app --factory --reload     # run → http://localhost:8000/docs
uv run ruff check . && uv run ruff format --check .       # lint
uv run mypy                                               # type-check (strict)
uv run pytest                                             # tests + coverage (warnings fail)

docker build -t aitp-api --build-arg GIT_SHA=$(git rev-parse --short HEAD) .
docker run --rm -p 8000:8000 aitp-api
```

From the repo root, `pnpm dev`, `pnpm lint`, `pnpm typecheck` and `pnpm test` run these too.
Settings come from environment variables (and the repo-root env file in local dev); see
`.env.example` and `app/core/config.py`.

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
