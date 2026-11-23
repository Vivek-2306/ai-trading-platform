# Progress

**Last updated:** 2026-11-23 (laptop)

## Current phase

Setup phases planned (Phase 1–6, AITP-1 … AITP-35). Waiting for the owner to review the
tickets and say "go" for Phase 1. No application code yet.

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

## In progress

Nothing. Waiting for the owner's review.

## Next up

1. Owner reviews tickets in Notion and says "go" for Phase 1 (this also counts as approving the stack).
2. On "go": first commit on `develop` ("chore: project setup" — `.gitignore`, `CLAUDE.md`,
   `docs/`, `infra/`), push `develop`, create `main` at that same commit, set `develop` as
   GitHub's default branch. Then branch `phase-1-repo-foundation` from `develop` and work
   AITP-1 … AITP-5.
3. Open the Phase 1 PR into `develop`, wait for owner review and merge.

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
