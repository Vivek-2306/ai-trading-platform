# AI Trading Platform

An AI-powered research and trading-signal assistant for Indian and international stocks,
crypto, Forex and derivatives. It analyses prices, indicators, news, fundamentals and macro
events, then recommends **Buy, Sell, Hold or NO TRADE** with entry, stop-loss, target,
position size, risk-to-reward and a confidence score.

> **Status:** setup complete (v0.1). No trading features yet. Nothing here is financial advice.

## Principles

- **Capital protection first.** A risk engine can veto any signal.
- **NO TRADE is a valid answer.** Low-confidence setups are skipped, not forced.
- **Explainable.** Every signal shows the indicators, news and model votes behind it.
- **Measured, not assumed.** Backtest → paper trading → small live capital, tracked by win
  rate, profit factor, drawdown and Sharpe ratio.
- **Automation last.** Live orders only with explicit approval and hard limits.

## Stack

| Layer | Tech |
| --- | --- |
| Backend | Python 3.13, FastAPI, Celery, PostgreSQL + TimescaleDB + pgvector, Redis |
| AI / ML | LightGBM, scikit-learn, vectorbt, TA-Lib, Claude API |
| Web | Next.js, Tailwind CSS, shadcn/ui, TradingView lightweight-charts |
| Mobile | Expo / React Native (later) |
| Tooling | uv, pnpm + Turborepo, Ruff, mypy, pytest, Biome, Vitest, Docker Compose |

## Repository layout

```
apps/api        Python backend (FastAPI, workers, engines)
apps/web        Next.js web app
apps/mobile     Expo mobile app (later)
packages/       Shared TypeScript packages
infra/          Docker Compose and deploy config
docs/           Plans, architecture, ADRs, progress
```

## Quickstart

Requirements: Node 24, pnpm 9, Python 3.13, uv, Docker, jq (used by the Claude Code format hook).
On macOS also `brew install libomp` (LightGBM) and `brew install gitleaks` (commit hook).

```bash
git clone https://github.com/Vivek-2306/ai-trading-platform.git && cd ai-trading-platform
cp .env.example .env     # optional: the defaults already work for local development
pnpm bootstrap           # installs JS + Python packages and the git hooks
pnpm infra:up            # Postgres + TimescaleDB + pgvector and Redis (Docker)
pnpm db:migrate          # create the database schema
pnpm check               # lint + typecheck + tests (everything should pass)
```

Run it:

```bash
cd apps/api && uv run uvicorn app.main:create_app --factory --reload   # API  http://localhost:8000/docs
pnpm --filter @aitp/web dev                                            # Web  http://localhost:3000
pnpm worker                                                            # background jobs (optional)
pnpm beat                                                              # schedules the hourly candle updates (optional)
pnpm stream                                                            # live 1m candles from Binance (optional)
pnpm tunnel                                                            # public URL for a phone/tablet
```

| Command | What it does |
| --- | --- |
| `pnpm check` | lint + typecheck + unit tests, all packages |
| `pnpm test:integration` | tests against real Postgres and Redis (starts its own containers) |
| `pnpm format` | auto-format everything |
| `pnpm api:postman` | regenerate the Postman collection after an API change |
| `pnpm --filter @aitp/api-client generate` | regenerate the typed web client after an API change |
| `pnpm infra:up` / `infra:down` | start / stop the local database and Redis |
| `pnpm stack:up` / `stack:down` | the full production stack on one server. First `cp infra/prod.env.example infra/prod.env` and fill it in |

## Docs

- [Architecture](docs/ARCHITECTURE.md)
- [Tech stack](docs/TECH_STACK.md)
- [Cost estimates](docs/COSTS.md)
- [Risks and compliance](docs/RISKS_AND_COMPLIANCE.md)
- [Plan](docs/PLAN.md) and [progress](docs/PROGRESS.md)
- [Decisions (ADRs)](docs/decisions/)

## Workflow

Work is tracked as Notion tickets (`AITP-n`). Each phase runs on a `phase-<n>-<slug>`
branch and merges into `develop` by pull request; releases go from `develop` to `main`.
See [CLAUDE.md](CLAUDE.md) for the full rules.
