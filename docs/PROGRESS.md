# Progress

**Last updated:** 2026-11-23 (laptop)

## Current phase

**Phase 2 — Backend API skeleton** on `phase-2-api-skeleton` (AITP-6 … AITP-11).
Phase 1 merged into `develop` (PR #1, merge `45fbeb7`) and closed out.

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

## In progress

Phase 2 PR #2 into `develop` (owner review): https://github.com/Vivek-2306/ai-trading-platform/pull/2
CI green (22 s). "API (Python)" is a required check on `main` and `develop` (branch must be
up to date before merging).

## Next up

1. Owner reviews and merges PR #2; then `/release-phase 2`.
2. Phase 3 — Local infrastructure and data layer (AITP-12 … AITP-17) after the owner says "go".
3. Open owner decision: the deny rule `Bash(* .env.*)` is too broad (blocks any command that
   merely mentions an env file name, e.g. commit messages). Proposed: narrow it to reader
   commands (cat/less/more/head/tail/grep/source).

## Open questions (owner decisions)

- [ ] Personal tool only, or a public product later? (drives SEBI registration + data licences)
- [ ] MVP markets: Indian equities + crypto first?
- [ ] Indian broker: Zerodha (Kite Connect), Upstox or Angel One?
- [ ] MVP hosting: low-cost server or AWS from day one?
- [ ] Monthly budget ceiling for the MVP.
- [ ] Mobile app phase (proposed: after web signals + paper trading).

These are needed before feature phases, not before setup Phases 1–6.

## Known issues

- Non-Claude prices in `docs/COSTS.md` are approximate and were not verified live.

## Session log

| Date | Env | Summary |
| --- | --- | --- |
| 2026-11-23 | laptop | Setup answers, prerequisites, plan doc, project memory files, Docker Compose decision |
| 2026-11-23 | laptop | GitHub repo created; Notion phases/tickets DBs + 35 tickets; PLAN.md; working mode → Claude implements, owner reviews PRs |
| 2026-11-23 | laptop | Branching → develop/main; first commit on develop; Phase 1 (AITP-1 … 5) implemented, PR opened |
