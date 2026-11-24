# Progress

**Last updated:** 2026-11-24 (laptop)

## Current phase

**Phase 4 — Web app skeleton** on `phase-4-web-skeleton` (AITP-18 … 23, plus AITP-36 env/logging and
AITP-37 ngrok tunnel). Phases 1–3 merged into `develop` (PRs #1–#3).
**Phase 4b — API reference, Postman, logging** (AITP-38 … 40) follows on `phase-4b-api-docs`.

## Last completed

- Setup Step 0 (answers) and Step 1 (prerequisites: git, gh as `Vivek-2306`, Node 24.1, pnpm 9.15,
  Python 3.13.3, uv 0.13.9, Docker 28.2.2, Notion) ✅
- Git repo initialised on `main` (no commits yet); GitHub repo created, public:
  https://github.com/Vivek-2306/ai-trading-platform ; remote `origin` set.
- Owner drafted `infra/docker-compose.dev.yml` (to be finalised in AITP-12).
- Notion set up: project page, Phases DB (6 rows), Tickets DB (35 tickets, views: Board,
  By phase, Blocked / Needs decision), Decisions page. Links in `CLAUDE.md`.
- `docs/PLAN.md` written with all six setup phases.
- Local git-ignored `private/` folder created for personal notes.
- Planning docs, ADR 0001 (stack, proposed) and ADR 0002 (Docker Compose, accepted).

- Owner said "go" (stack approved, ADR 0001 Accepted). First commit `bbd94fc` on `develop`;
  `main` created at the same commit; `develop` is GitHub's default branch.
- Phase 1: AITP-1 monorepo root (`d680fa6`), AITP-2 README/CHANGELOG/.env.example (`9e17c0a`),
  AITP-3 GitHub templates (`9e2932e`), AITP-4 Claude settings + format hook (`ef0bf7c`),
  AITP-5 slash commands.

- Phase 1 merged (PR #1). Branch protection on `main` and `develop` since 2026-11-23.
- Phase 2: AITP-6 Python project in `apps/api` (uv, Python 3.13, core deps, module layout).
- AITP-7 Ruff/mypy strict/pytest+coverage, wired into root `pnpm` scripts; format hook
  proved working on a `.py` edit.
- AITP-8 FastAPI `create_app()` factory, settings, `/health`, `/version`, `/docs`; 10 tests, 100% coverage of app code.
- AITP-9 structlog (JSON in prod), X-Request-ID middleware, consistent JSON errors; 24 tests.
- AITP-10 Dockerfile (`1423cb4`): image builds (263 MB), container answers `/health` and
  `/version`, runs as non-root `app`, JSON logs. (Docker Desktop needed the owner's macOS
  password once.)
- AITP-11 CI workflow (`.github/workflows/ci.yml`, job "API (Python)"), with image smoke test.
- Self-review fixes applied (headers on errors, no input echo, CORS wildcard rejected, 500s logged,
  JSON-only prod logs); 34 tests.

- Phase 2 merged (PR #2). "API (Python)" is a required check on `main` and `develop`.
- Phase 3: AITP-12 dev Compose stack (TimescaleDB 2.32 + pgvector 0.8 verified, Redis 7), `pnpm infra:*`.
- AITP-13 async SQLAlchemy engine/sessions, `Base` naming conventions, `/health/ready` (verified 200 against dev DB, 503 when down); 41 tests.
- AITP-14 Alembic + baseline migration `0001` (timescaledb, vector); upgrade/downgrade/upgrade verified on dev DB and from the image; 44 tests.
- AITP-15 async Redis client + readiness check (live: 200 → 503 when Redis stopped → 200); 46 tests.
- AITP-16 Celery app + `ping`/`heartbeat` tasks, beat schedule; live round-trip through Redis verified; 51 tests.
- AITP-17 integration tests (5) with testcontainers, in CI; dev DB image switched to pinned `timescale/timescaledb:2.32.1-pg17`.
- Self-review fixes (`%` in DB passwords, startup cleanup, Celery visibility timeout and no redelivery loops, heartbeat results off, `pnpm beat` on fresh clones); 53 unit + 5 integration tests.

- Phase 3 merged (PR #3, `892f48f`). Phase 4 started: AITP-18 Next.js 16 app in `apps/web` (strict TS, `/api/*` proxied to the API, repo-root env file loaded).
- AITP-19 responsive glass UI shell (Tailwind v4, dark/light, bottom nav on phones), AITP-20 Biome + Vitest, AITP-21 `packages/api-client` generated from OpenAPI (CI checks it is fresh), AITP-22 live system status page (API/DB/Redis; verified Redis down → shows Down), AITP-36 validated env + pino logs + one request ID across web and API logs, AITP-37 `pnpm tunnel` (ngrok; verified from the public URL), AITP-23 web CI job. 10 web tests.

## In progress

Phase 4 finishing: self-review, then PR into `develop`.

## Next up

1. Owner reviews and merges the Phase 4 PR; then `/release-phase 4`.
2. Phase 4b (AITP-38 … 40): Notion API Reference, Postman collection, logging hardening.
3. Owner: add `API_URL=http://127.0.0.1:8000`, `POSTGRES_PORT=5432`, `REDIS_PORT=6379` to `.env.example`
   (Claude cannot edit that file), and run `cp .env.example .env` for local use.
4. Owner decision: narrow the over-broad `Bash(* .env.*)` deny rule (it blocks harmless commands).

## Open questions (owner decisions)

- [ ] Personal tool only, or a public product later? (drives SEBI registration + data licences)
- [ ] MVP markets: Indian equities + crypto first?
- [ ] Indian broker: Zerodha (Kite Connect), Upstox or Angel One?
- [ ] MVP hosting: low-cost server or AWS from day one?
- [ ] Monthly budget ceiling for the MVP.
- [ ] Mobile app phase (proposed: after web signals + paper trading).

These are needed before feature phases, not before setup Phases 1–6.

## Known issues

- Old dev volume `aitp_db-data` (from the previous timescaledb-ha image) is unused; the owner
  can delete it with `docker volume rm aitp_db-data` (it only held an empty dev database).

- Non-Claude prices in `docs/COSTS.md` are approximate and were not verified live.

## Session log

| Date | Env | Summary |
| --- | --- | --- |
| 2026-11-23 | laptop | Setup answers, prerequisites, plan doc, project memory files, Docker Compose decision |
| 2026-11-23 | laptop | GitHub repo created; Notion phases/tickets DBs + 35 tickets; PLAN.md; working mode → Claude implements, owner reviews PRs |
| 2026-11-23 | laptop | Branching → develop/main; first commit on develop; Phase 1 (AITP-1 … 5) implemented, PR opened |
