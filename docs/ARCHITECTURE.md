# Architecture

Status: approved 2026-11-23.

One Python backend (a modular monolith) running as three process types, with one PostgreSQL
database. A risk engine sits between every signal and the user.

## System overview

```
1 SOURCES   Market data │ News & filings │ Macro & calendar │ Fundamentals
                 │
2 INGEST    Ingestion workers + stream service (scheduled pulls, live streams,
                 │                                clean, align time zones, de-dupe)
3 STORE     TimescaleDB (candles, ticks) │ PostgreSQL (users, signals, trades, audit)
                 │                         │ Redis (live prices, cache, queue) │ pgvector (news)
4 ANALYSE   Technical │ Fundamental │ News & sentiment (LLM) │ ML models
                 │ votes
5 DECIDE    Signal engine ──▶ RISK ENGINE ──▶ Decision: trade (entry, stop, target, size)
                 ▲            (can veto)       or NO TRADE + reason
                 │                                   │
6 ACT       Backtest & tracking ◀──┬── Execution (paper first; orders only after approval)
            (results re-weight     └── Alerts (push, Telegram, email)
             the signal engine)          │
7 SHOW      Web app (Next.js) ◀── API (FastAPI, REST + WebSocket) ──▶ Mobile app (Expo)
```

## How the pieces run

| Component | Runs as | Job |
| --- | --- | --- |
| API | FastAPI app | REST endpoints, live prices over WebSocket, login |
| Stream service | Long-running async process | WebSocket feeds from brokers/exchanges → Redis + TimescaleDB |
| Workers | Celery workers + Celery Beat | Scheduled data pulls, news processing, analysis runs, backtests, training |
| Analysis, signal, risk engines | Python modules inside workers | Indicators, model votes, final decision, stop-loss and sizing |
| Execution service | Separate worker with its own kill switch | Paper trades by default; real orders only for approved strategies within limits |
| Web app | Next.js on Vercel | Dashboards, charts, signal history, reports |
| Mobile app | Expo (iOS + Android) | Signals, alerts, one-tap trade approval |

Backend modules: `data`, `analysis`, `signals`, `risk`, `execution`, `backtest`. A module
becomes its own service only when load or isolation demands it (execution is likeliest first).

## How the AI decides

1. **Rules layer (no AI):** RSI, MACD, moving averages, ATR, VWAP, candlestick patterns,
   support/resistance. Plain, tested code.
2. **ML layer:** LightGBM models on engineered features predict up/down probability over a
   horizon. Trained offline, versioned (MLflow), re-validated walk-forward.
3. **LLM layer:** reads news, filings, economic events; extracts events and sentiment; writes
   the plain-English reasoning. Claude Haiku 5.5 for bulk tagging, Claude Opus 5.5 for final
   reasoning on shortlisted candidates only.
4. **Ensemble:** each layer votes; per-market weights come from backtest/paper results;
   calibrated confidence; below threshold → NO TRADE.
5. **Risk gate:** ATR-based stop-loss, target, position size (fixed-fractional, capped Kelly),
   user limits. Can veto any signal; no model overrides it.

Against fake accuracy: walk-forward only, no look-ahead data, costs + slippage modelled, a
locked out-of-sample period nobody tunes on.

## Data

- **TimescaleDB:** candles and ticks per instrument/timeframe, continuous aggregates
  (1m → 5m → 1h → 1d), compression.
- **PostgreSQL:** users, instruments, signals, trades, settings, audit log.
- **pgvector:** embeddings of news and filings for LLM context search.
- **Redis:** latest prices, pub/sub to WebSocket, Celery broker.
- **Object storage (S3 / Cloudflare R2):** model files, backtest reports, raw news archive.

## Security

- Broker API keys encrypted at rest, backend-only, never sent to apps.
- Secrets in a secrets manager (Doppler/Infisical); `.env` stays local, never committed.
- Two-factor login required before live trading can be enabled.
- Live limits: max loss/day, max capital share per trade, max open positions, kill switch.
- Append-only audit log of every signal, approval and order.

## Deployment path

Docker Compose throughout dev, MVP and beta; no Kubernetes for now (ADR 0002).

0. **Development (local, $0):** Compose runs Postgres + TimescaleDB and Redis; API and web
   run natively for hot reload.
1. **MVP:** one server in Mumbai/Bangalore, Docker Compose (API, workers, stream,
   Postgres + TimescaleDB, Redis); web on Vercel.
2. **Beta:** managed database with backups, second server for workers, Sentry, uptime alerts.
3. **Production:** AWS Mumbai, containers (ECS Fargate) with autoscaled workers, Timescale
   Cloud, read replica, deploys from GitHub Actions.

Indian brokers may require orders from a registered static IP; a fixed server address covers it.

## Folder layout (planned)

```
apps/api/        Python package: app/{api,data,analysis,signals,risk,execution,backtest}, tests/
apps/web/        Next.js app
apps/mobile/     Expo app (later phase)
packages/api-client/  TS client generated from the FastAPI OpenAPI spec
packages/ui/     shared TS types, formatting, constants
infra/           Docker Compose, deploy config
docs/            plans, ADRs, progress
```

## Conventions

- Money and prices: `Decimal` in Python, never float, for anything that sizes or places orders.
- Timestamps stored in UTC; convert to exchange time zone only for display and market hours.
- Every external API sits behind an adapter interface with contract tests.
- API types flow one way: FastAPI OpenAPI → generated TS client; no hand-written duplicates.
