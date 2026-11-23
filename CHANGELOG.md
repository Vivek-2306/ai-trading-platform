# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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

### Changed

- Tightened Claude Code permissions after self-review: pushes allowed only to `phase-*`
  branches and tags; refspec, mirror, delete and force pushes denied; all `gh api` calls
  prompt; every env file is unreadable; destructive git commands prompt (AITP-4).
- Workflow: merge `origin/develop` into phase branches instead of rebasing; blocked tickets
  are skipped inside a phase; CHANGELOG updated once per ticket (AITP-5).

[Unreleased]: https://github.com/Vivek-2306/ai-trading-platform/compare/main...develop
