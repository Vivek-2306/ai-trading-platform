# Setup report: v0.1.0

**Date:** 2026-11-24. **Scope:** everything needed before feature work starts. No trading features exist yet.

## What was built

| Phase | PR | Result |
| --- | --- | --- |
| 1. Repo foundation and workflow | #1 | Monorepo (pnpm + Turborepo), GitHub templates, CODEOWNERS, Claude Code settings and slash commands |
| 2. Backend API skeleton | #2 | FastAPI app factory, typed settings, structured logs, request IDs, one error format, Docker image, CI |
| 3. Local infrastructure and data layer | #3 | TimescaleDB + pgvector and Redis (Compose), async SQLAlchemy, Alembic, readiness endpoint, Celery worker and beat, integration tests |
| 4. Web app skeleton | #4 | Next.js app with a responsive glass UI, status page, typed API client generated from OpenAPI, pino logs, phone tunnel, web CI |
| 4b. API reference, Postman, logging | #5 | Notion API Reference, generated Postman collection, secret-safe logs, optional log file and Sentry |
| 5. Domain packages | #6 | `analysis`, `ml`, `ai`, `markets` dependency groups with smoke tests; Dependabot |
| 6. Quality gates, deploy base, release | #7 | Pre-commit hooks, secret scanning, production Compose stack, verified quickstart, full branch protection |

## Numbers

- 35 setup tickets plus 5 added later (AITP-1 … AITP-40), all tracked in Notion.
- 106 API unit tests, 5 integration tests (real Postgres and Redis), 20 web tests.
- 4 required CI jobs on `main` and `develop`: API (Python), Web (TypeScript), Packages (import smoke), Secret scan (gitleaks).
- Quickstart checked from a fresh clone: bootstrap, migrate and `pnpm check` all pass.
- Production stack checked end to end locally: migrations run, status page shows API, database and Redis healthy; only Caddy is exposed.

## Safety rules in place

- Nothing merges without a pull request and green CI; admins are not exempt; no force pushes.
- Secrets: git-ignored env files, a commit hook and a CI scan of the full history (gitleaks), log redaction, hidden secret settings.
- The public tunnel exposes the web app only, and only three read-only API paths.
- `TRADING_MODE` defaults to `paper`. No live-trading code exists.

## Known gaps and findings

- **No NSE holiday calendar** in `exchange-calendars` (BSE only). Needs its own data in a feature phase.
- **QuantStats pulls in yfinance** (Yahoo scraping): fine for research, not a production data source.
- **The Docker image does not include the `analysis`/`ml`/`ai`/`markets` groups yet.** Add `--group` in `apps/api/Dockerfile` (and `libgomp1`) when app code needs them.
- **`.env.example` is out of date** (Claude cannot edit it): add `API_URL`, `POSTGRES_PORT`, `REDIS_PORT`, `LOG_FILE`, `SENTRY_DSN`, `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`.
- **No server is provisioned.** `infra/docker-compose.prod.yml` is ready; it needs a host and a domain (hosting decision below).
- The `Bash(* .env.*)` deny rule is broader than needed and blocks harmless commands (for example, commit messages that mention an env file).

## Decisions needed before feature work

- [ ] Personal tool only, or a public product later? (drives SEBI registration and data licences)
- [ ] MVP markets: Indian equities + crypto first?
- [ ] Indian broker: Zerodha (Kite Connect), Upstox or Angel One?
- [ ] MVP hosting: low-cost server or AWS from day one?
- [ ] Monthly budget ceiling for the MVP.
- [ ] Mobile app phase timing.

## Suggested first feature phases

1. Market data ingestion (one source, one market) into TimescaleDB, with data-quality checks.
2. Indicator engine (TA-Lib) and a first backtest harness with realistic costs.
3. Risk engine (position sizing, stop-loss, daily loss limit, NO TRADE gate) before any signal logic.
4. Signal generation with explanations; paper trading and accuracy tracking.
