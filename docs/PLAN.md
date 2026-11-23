# Plan

Source of truth for scope. Notion is the source of truth for status
(Tickets DB: https://app.notion.com/p/421426f94e2f817ba5d5d4591d2b4b3c).
Full acceptance criteria live in each Notion ticket; the summary here must stay in sync.

Phase size rule: 5–8 tickets, roughly ≤600 changed lines per PR; split bigger phases (3a/3b).
One branch and one PR per phase, cut from and merged into `develop`. The owner reviews
tickets and PRs and merges. Releases go `develop` → `main` by PR (first one at v0.1.0).

## Setup phases (foundation, before feature work) — planned 2026-11-23

### Phase 1 — Repo foundation and workflow (`phase-1-repo-foundation`)

**Goal:** monorepo skeleton, project docs, GitHub templates, Claude Code settings and commands.

- AITP-1 Monorepo root workspace: pnpm workspace, Turborepo, root scripts, `.editorconfig`, `.nvmrc`, `.python-version`, folders
- AITP-2 Repo docs: README, CHANGELOG, `.env.example`, git-ignored local `private/` folder
- AITP-3 GitHub templates: PR template, issue templates, CODEOWNERS
- AITP-4 Claude Code `.claude/settings.json` (allow/deny) + format hook
- AITP-5 Claude Code slash commands (8 workflow commands)

**Out of scope:** any Python or web app code.

### Phase 2 — Backend API skeleton (`phase-2-api-skeleton`)

**Goal:** FastAPI app in `apps/api` with health endpoints, tooling, Dockerfile and Python CI.

- AITP-6 Python project in `apps/api` with uv (core deps only, module layout)
- AITP-7 Ruff, mypy strict, pytest + coverage; wired into root scripts
- AITP-8 FastAPI app factory, settings, `/health`, `/version`, OpenAPI
- AITP-9 Structured logging, request IDs, consistent error responses
- AITP-10 API Dockerfile (multi-stage, non-root, healthcheck)
- AITP-11 CI workflow: Python job

**Out of scope:** database, workers, trading logic.

### Phase 3 — Local infrastructure and data layer (`phase-3-data-layer`)

**Goal:** Compose dev stack and the async data layer.

- AITP-12 Dev Compose: TimescaleDB (+pgvector) and Redis, healthchecks, `pnpm infra:*` scripts
- AITP-13 Async SQLAlchemy 2 engine/sessions, `/health/ready` checks DB
- AITP-14 Alembic + baseline migration enabling `timescaledb` and `vector`
- AITP-15 Redis client, readiness check per dependency, 503 when down
- AITP-16 Celery worker + beat skeleton (`ping`, heartbeat)
- AITP-17 Integration tests with real Postgres and Redis (testcontainers), run in CI

**Out of scope:** market-data tables and ingestion.

### Phase 4 — Web app skeleton (`phase-4-web-skeleton`)

**Goal:** Next.js shell talking to the API through a typed client.

- AITP-18 Next.js app in `apps/web` (TS strict)
- AITP-19 Tailwind + shadcn/ui app shell, dark mode, phone width
- AITP-20 Biome + `tsc` + Vitest/Testing Library, wired into Turborepo
- AITP-21 `packages/api-client` generated from OpenAPI; CI fails if stale
- AITP-22 System status page (API, DB, Redis)
- AITP-23 CI workflow: web job

**Out of scope:** real dashboards, charts, auth. Mobile app deferred.

### Phase 5 — Domain packages and dependency management (`phase-5-domain-deps`)

**Goal:** every package the features need, installed and smoke-tested.

- AITP-24 `analysis` group: pandas, NumPy, Polars, TA-Lib, SciPy, statsmodels, vectorbt, QuantStats, exchange-calendars
- AITP-25 `ml` group: scikit-learn, LightGBM, Optuna, MLflow, SHAP
- AITP-26 `ai` group: anthropic, voyageai, pgvector + settings fields
- AITP-27 `markets` group: kiteconnect, ccxt, alpaca-py, polygon-api-client, finnhub-python, fredapi, feedparser, trafilatura, python-telegram-bot, websockets, tenacity (no OANDA for now)
- AITP-28 Import smoke tests for every package, in CI
- AITP-29 Dependabot for uv, npm, Actions, Docker

**Out of scope:** using the packages.

### Phase 6 — Quality gates, deploy base and v0.1.0 (`phase-6-quality-deploy`)

**Goal:** safety nets, a deployable Compose stack, and the first release.

- AITP-30 Pre-commit hooks (Ruff, Biome, gitleaks, whitespace)
- AITP-31 Secret scanning (gitleaks) in CI
- AITP-32 Full-stack Compose for the MVP server (api, worker, beat, db, redis, Caddy)
- AITP-33 Developer commands + quickstart verified from a fresh clone
- AITP-34 Branch protection on main via `gh api`
- AITP-35 Release v0.1.0 and setup report

**Out of scope:** provisioning a real server (needs the hosting decision).

## Feature phases

Not planned yet. After v0.1.0, run `/plan-project` with the owner's answers to the open
decisions (markets, broker, personal vs public, mobile timing).
