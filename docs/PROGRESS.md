# Progress

**Last updated:** 2026-11-23 (laptop)

## Current phase

**Phase 3 — Local infrastructure and data layer** on `phase-3-data-layer` (AITP-12 … AITP-17).
Phases 1 and 2 merged into `develop` (PR #1 `45fbeb7`, PR #2 `69227c1`) and closed out.

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

## In progress

Phase 3 PR #3 into `develop` (owner review): https://github.com/Vivek-2306/ai-trading-platform/pull/3
CI green in 1m14s, including integration tests against real TimescaleDB + Redis.

## Next up

1. Owner reviews and merges PR #3; then `/release-phase 3`.
2. Phase 4 — Web app skeleton (AITP-18 … AITP-23) after the owner says "go".
3. Owner decisions on permissions:
   - The deny rule `Bash(* .env.*)` is too broad (blocks any command that merely mentions an
     env file name, e.g. commit messages). Proposed: narrow it to reader commands.
   - `Read(**/.env.*)` also blocks *editing* the example env file. Pending addition there:
     `POSTGRES_PORT=5432` and `REDIS_PORT=6379` (optional; the compose file has defaults).
     Either the owner adds them, or allows Claude to edit the example file.

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
