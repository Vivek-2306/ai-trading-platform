# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `instruments` and `candles` tables (candles is a TimescaleDB hypertable with exact `NUMERIC` prices, UTC times, one row per instrument, timeframe and open time) and migration `0002` (AITP-41).
- Market data adapter interface and a Binance public-data adapter (`ccxt`, no API key): closed candles only, exact `Decimal` prices, retries with backoff on rate limits, reusable contract test. `ccxt` and `tenacity` are now runtime dependencies so the worker image has them (AITP-42).
- Twelve Data adapter for XAU/USD gold, enabled by the optional `TWELVE_DATA_API_KEY`; gold defaults to `PAXG/USDT` on Binance without a key. The API key never appears in errors or logs (AITP-43).

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
