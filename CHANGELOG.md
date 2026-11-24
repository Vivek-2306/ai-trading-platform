# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Indicator library (`app/analysis/indicators.py`, TA-Lib): SMA, EMA, RSI, MACD, ATR, Bollinger bands and a rolling VWAP. Warm-up values are NaN, never invented; tested against independent long-hand implementations. `ta-lib` and `numpy` are now runtime dependencies (AITP-55).
- Feature pipeline (`app/analysis/features.py`): indicator values aligned to every candle for any timeframe, and `find_lookahead`, which proves no feature at candle t changes when later candles are removed (a deliberately leaky feature is caught) (AITP-56).
- `signals` table (migration `0004`): action BUY/SELL/HOLD/NO_TRADE, confidence 0 to 1, reasons and the feature inputs as JSON, rule version; one row per instrument, timeframe, candle and rule version. Append-only: the database rejects UPDATE, DELETE and TRUNCATE (AITP-57).
- Rule engine `rules-v1` (`app/signals/rules.py`): six plain rules (trend, price vs average, MACD momentum, RSI, Bollinger band, VWAP) vote with weights and reasons; the result is BUY, SELL, HOLD or NO_TRADE with a 0 to 1 agreement score. NO_TRADE on too little data, extreme volatility, conflicting indicators or weak agreement. Deterministic and explainable; thresholds in `RuleConfig` (AITP-58).
- Hourly `run_signals` job (Celery beat, 10 minutes past the hour, after the candle update): decides for the newest closed 1h and 1d candle of every tracked instrument and appends the signal. One signal per instrument, timeframe, candle and rule version, so reruns store nothing new; stale data (newest candle older than 3 candle lengths) is skipped; one failing instrument does not stop the rest (AITP-59).
- `GET /signals` (filter by instrument, timeframe or action; newest first; paged with `before_id`) and `GET /signals/latest` (newest per instrument and timeframe). Read-only. Postman and the typed web client regenerated (AITP-60).
- Live stream service (`pnpm stream`, `python -m app.stream`): follows Binance 1-minute candles over WebSocket for every tracked Binance instrument, reconnects with growing backoff, stops promptly on SIGTERM, and refreshes a Redis heartbeat that the new `stream` container health check reads (AITP-49).
- Stream candles are stored: the forming 1m candle goes to Redis (`live:binance:<symbol>:1m` plus a pub/sub channel) and each closed candle is written to TimescaleDB once its final values have arrived; a candle cut short by a disconnect is skipped for the REST backfill. Verified identical to Binance REST for live BTC/USDT candles (AITP-50).
- Stream gap healing: the stream service refetches the last day of 1m candles over REST at startup, after every reconnect and every 5 minutes, logs and refills any holes (including candles cut short by a disconnect) (AITP-51).
- Migration `0003`: TimescaleDB continuous aggregates `candles_5m_agg` and `candles_1h_agg` built from 1m candles (real-time, with a per-bucket candle count so partial buckets are visible), compression of chunks older than 7 days, and a daily job deleting 1m candles older than `CANDLE_1M_RETENTION_DAYS` (default 90, 0 keeps all; the aggregates, 1h and 1d candles are kept). `GET /data/candles?timeframe=5m` serves complete 5-minute buckets from the aggregate (AITP-52).
- `GET /data/stream?symbol=BTC/USDT`: live forming-candle updates as Server-Sent Events relayed from Redis. Slow clients get only the newest update, quiet streams send keepalives, at most 50 streams at once, unknown symbols are rejected, and slots and Redis subscriptions are released when a client leaves (AITP-53).
- Web `/charts` shows a live price and a Live / Reconnecting badge for Binance instruments, and the current candle moves in real time without redrawing the chart. The proxy forwards `/api/data/stream` only, with a validated `symbol` and nothing else. The stream response is marked `no-transform` because the web server's compression otherwise held events back for browsers (AITP-54).
- Hardening from review: REST data is authoritative (it corrects a stream-stored candle and settles 5 s before a candle counts as closed), the aggregates are refreshed after heals, the stream exits for a restart if no update arrives for 3 minutes and survives Redis or database blips, SSE cleanup is shielded from request cancellation, and the chart's 1h/1d forming candle is seeded from 5-minute candles.

- `instruments` and `candles` tables (candles is a TimescaleDB hypertable with exact `NUMERIC` prices, UTC times, one row per instrument, timeframe and open time) and migration `0002` (AITP-41).
- Market data adapter interface and a Binance public-data adapter (`ccxt`, no API key): closed candles only, exact `Decimal` prices, retries with backoff on rate limits, reusable contract test. `ccxt` and `tenacity` are now runtime dependencies so the worker image has them (AITP-42).
- Twelve Data adapter for XAU/USD gold, enabled by the optional `TWELVE_DATA_API_KEY`; gold defaults to `PAXG/USDT` on Binance without a key. The API key never appears in errors or logs (AITP-43).
- Historical backfill: `backfill_candles` Celery task loads N years for an instrument and timeframe page by page, logs progress, and is safe to re-run (existing candles are skipped). Default instrument list in `app/data/universe.py` (AITP-44).
- Hourly `update_candles` job (Celery beat, 2 minutes past the hour): fetches new candles for every tracked instrument, finds holes in the last 30 days and refills them. Market-hours aware: spot gold's weekend closure is not a gap, while crypto never closes. One failing instrument does not stop the rest (AITP-45).
- `GET /data/quality`: per instrument and timeframe, missing candles, stale data, inconsistent candles and price spikes over the last 30 days, shown on the web status page. Postman collection and typed web client regenerated (AITP-46).
- `GET /data/instruments` and `GET /data/candles` (newest-first paging with `before` / `next_before`, up to 1000 per page, prices as exact decimal strings) (AITP-47).
- Web `/charts` page: candlestick chart (lightweight-charts) with instrument and 1h/1d pickers, dark/light aware, responsive with a bottom-nav entry on phones, loading, empty and error states. Checked in a phone-sized browser against real Binance data (AITP-48).

## [0.1.0] - 2026-11-24

First release: the complete project setup. There are no trading features yet.

### Added

- Production Compose stack for one server (web, API, worker, beat, database, Redis, Caddy with automatic HTTPS), web Docker image, `infra/prod.env.example` (AITP-32).
- Pre-commit hooks (`pnpm hooks:install`: whitespace, Ruff, Biome, gitleaks) and a CI secret scan of the full git history (AITP-30, AITP-31).
- Dependency groups `analysis`, `ml`, `ai`, `markets` (uv, install with `--all-groups`), AI settings fields, import smoke tests (CI job "Packages"), and Dependabot for uv, npm, Actions and Docker (AITP-24 … 29).
- Postman collection generated from OpenAPI (`docs/api/`, `pnpm api:postman`, CI-checked), Notion API Reference database, and logging hardening: secret redaction, quiet health probes, optional rotating `LOG_FILE`, optional Sentry via `SENTRY_DSN` (AITP-38 … 40).
- Web app (`apps/web`): Next.js 16, responsive glass UI with dark/light themes, live system status page, Biome and Vitest, typed API client generated from OpenAPI, validated env, pino logs with request IDs shared with the API, `pnpm tunnel` for phone/tablet previews, web CI job (AITP-18 … 23, 36, 37).
- Monorepo root: pnpm workspace, Turborepo pipelines, editor and runtime version files (AITP-1).
- README, CHANGELOG and `.env.example` (AITP-2).
- GitHub PR template, issue templates and CODEOWNERS (AITP-3).
- Claude Code project settings: permission guardrails and a format-on-edit hook (AITP-4).
- Claude Code workflow commands: `/plan-project`, `/start-phase`, `/work-phase`,
  `/work-ticket`, `/phase-status`, `/handoff`, `/address-review`, `/release-phase` (AITP-5).
- Planning docs, ADRs 0001–0002 and the local dev Compose file (project setup).
- Branch protection on `main` and `develop`: PR required, no force pushes or deletions,
  admins included, conversations must be resolved (part of AITP-34, done early).
- Python backend project in `apps/api`: uv, Python 3.13, FastAPI/Uvicorn/Pydantic/structlog/httpx,
  module layout for api, core, data, analysis, signals, risk, execution, backtest (AITP-6).
- Python tooling: Ruff (lint + format), mypy strict, pytest with coverage; `pnpm lint`,
  `typecheck`, `test` and `format` now include the backend (AITP-7).
- FastAPI app factory with typed settings from the environment, `GET /health`,
  `GET /version`, OpenAPI at `/docs`; `pnpm dev` runs the API (AITP-8).
- Structured logging (JSON in production, readable in dev), an `X-Request-ID` on every
  request, response and log line, and one JSON error format with no stack traces (AITP-9).
- API Dockerfile: multi-stage uv build, slim non-root runtime, healthcheck on `/health`,
  `GIT_SHA` build arg; settings no longer assume the monorepo layout at runtime (AITP-10).
- GitHub Actions CI: on PRs and pushes to `develop`/`main`, the API job installs with a uv
  cache, runs Ruff, mypy and pytest, builds the Docker image and smoke-tests it; actions
  pinned to commit SHAs (AITP-11).
- Self-review fixes: error responses keep headers like `Allow`; validation errors no longer
  echo submitted values; `CORS_ORIGINS=*` is rejected; failed requests are still logged
  with status 500 and request context is cleared after each request; uvicorn/stdlib logs
  are JSON in production and the duplicate access log is off (AITP-8 … AITP-11).
- Dev Compose stack finalised: Postgres 17 + TimescaleDB + pgvector and Redis 7 with
  healthchecks, named volumes, localhost-only ports and env-driven credentials;
  `pnpm infra:up/down/logs/ps` (AITP-12).
- Async database layer: SQLAlchemy 2 + asyncpg engine created at startup and disposed at
  shutdown, a per-request session dependency, a declarative base with constraint naming
  conventions, and `GET /health/ready` (503 when a dependency is down) (AITP-13).
- Alembic migrations (async, URL from settings, dated file names) with a baseline that enables
  TimescaleDB and pgvector; `pnpm db:migrate`; migrations ship in the Docker image (AITP-14).
- Async Redis client created at startup and closed at shutdown; `/health/ready` reports
  database and Redis separately (AITP-15).
- Celery worker and beat on Redis (JSON-only, acks-late, one task at a time, UTC, structlog
  logging) with a `ping` task and a minutely `heartbeat`; `pnpm worker` / `pnpm beat` (AITP-16).
- Integration tests against real TimescaleDB and Redis via testcontainers (migrations
  up/down/up, readiness healthy and unhealthy, DB session and Redis round-trips), run in CI;
  `pnpm test:integration` (AITP-17).
- Self-review fixes: migrations accept URL-encoded passwords containing `%`; the app's
  startup closes already-opened clients if a later step fails; Celery tasks are redelivered
  only after a 6-hour visibility timeout (configurable) and never after crashing a worker;
  the heartbeat stores no results; `pnpm beat` works on a fresh clone (AITP-13 … AITP-17).

### Changed (Phase 3)

- Dev database image switched from `timescaledb-ha:pg17` (3.7 GB) to the pinned
  `timescale/timescaledb:2.32.1-pg17` (same TimescaleDB 2.32.1 + pgvector 0.8.7, smaller),
  shared by dev, tests and CI (AITP-17).

### Changed

- Tightened Claude Code permissions after self-review: pushes allowed only to `phase-*`
  branches and tags; refspec, mirror, delete and force pushes denied; all `gh api` calls
  prompt; every env file is unreadable; destructive git commands prompt (AITP-4).
- Workflow: merge `origin/develop` into phase branches instead of rebasing; blocked tickets
  are skipped inside a phase; CHANGELOG updated once per ticket (AITP-5).

[Unreleased]: https://github.com/Vivek-2306/ai-trading-platform/compare/main...develop
