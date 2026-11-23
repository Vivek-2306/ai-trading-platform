# AI Trading Platform

An AI-powered research and trading-signal assistant for Indian and international stocks,
crypto, Forex and derivatives. It analyses prices, indicators, news, fundamentals and macro
events, then recommends **Buy, Sell, Hold or NO TRADE** with entry, stop-loss, target,
position size, risk-to-reward and a confidence score.

> **Status:** early setup (v0.x). No trading features yet. Nothing here is financial advice.

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

```bash
cp .env.example .env          # fill in values; never commit .env
pnpm install                  # TypeScript workspace tooling
docker compose -f infra/docker-compose.dev.yml up -d   # Postgres + TimescaleDB, Redis
pnpm lint && pnpm typecheck && pnpm test
```

App start commands will be added as the API and web app land (setup Phases 2–4).

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
