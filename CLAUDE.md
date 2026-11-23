# AI Trading Platform

AI-powered research and trading-signal assistant for Indian and international stocks,
crypto, Forex and derivatives. It analyses prices, indicators, news, fundamentals and
macro events, then outputs **Buy / Sell / Hold / NO TRADE** with entry, stop-loss,
target, position size, risk-to-reward and a confidence score. Automated trading is
optional, comes last, and only runs behind user approval and hard risk limits.

Principles: capital protection first · NO TRADE beats a low-confidence signal ·
every signal is explainable and logged · accuracy is measured, never assumed
(the "99.9%" target is an aspiration; real metrics are win rate, profit factor,
max drawdown, Sharpe; backtest → paper → small live) · deterministic core
(indicators, risk, orders) with AI on top; an LLM never sizes or places orders.

## Current state (auto-loaded)

@docs/PROGRESS.md

## Working mode (owner's choice, 2026-11-23)

- **Claude implements ticket by ticket; the owner reviews.** (Updated 2026-11-23; replaces
  the earlier "suggest in chat only" mode.) Claude does the work on the phase branch, one
  Notion ticket at a time, keeps every ticket's status, commit and checklist accurate, and
  opens one PR per phase. The owner reviews tickets and PRs and merges. Never merge yourself.
- Start a phase only after the owner says "go" for it. Stop and ask when a ticket needs a
  decision.
- Keep project memory current: `docs/PROGRESS.md`, `docs/PLAN.md`, ADRs.
- Repo is public. Anything personal (budget, broker account, capital limits, notes) goes in
  the git-ignored local `private/` folder, never in the repo.
- Keep development cost near zero: free tiers, local Docker, no paid services until needed.
- Containers: Docker Compose for dev, MVP and beta; no Kubernetes for now (ADR 0002).

## Start of every session

1. Read the progress file above. Once phases exist, read the current phase in `docs/PLAN.md`.
2. If setup is not finished, continue from the first unchecked step in `docs/SETUP_PLAN.md`.
3. Once a git repo exists: `git pull`.
4. Once Notion tickets exist: if any ticket in the current phase is "In Progress" with a
   different "Locked by" than this environment (laptop / cloud), STOP and ask the owner.
5. Don't ask the owner to re-explain the project; everything is in these files.
   If something is missing, ask one specific question and record the answer in the docs.

## Key facts

| Item | Value |
| --- | --- |
| GitHub repo | https://github.com/Vivek-2306/ai-trading-platform (public) |
| Ticket prefix | `AITP` (AITP-1, AITP-2, …), Notion unique ID |
| Notion project page | https://app.notion.com/p/421426f94e2f81a5a3ffe939fed31e4f |
| Notion Tickets DB | https://app.notion.com/p/421426f94e2f817ba5d5d4591d2b4b3c — data source `collection://421426f9-4e2f-81fe-b895-000bfd3b207d` |
| Notion Phases DB | https://app.notion.com/p/421426f94e2f812ab1a2fb146263d979 — data source `collection://421426f9-4e2f-811e-85fe-000b2bec0b99` |
| Notion Decisions page | https://app.notion.com/p/421426f94e2f81ff8c34c1a87dc1b426 |

Ticket properties: Title, ID, Status (To Do, In Progress, Blocked, Needs Decision, In Review,
Done), Phase, Phase page (relation to Phases DB), Type, Priority, Branch, Commit, PR,
Locked by (laptop, cloud). Acceptance criteria = to-do checklist in the ticket body; tick
each item when it's met. Phase rows track Status, Branch, PR and Release tag.
| Plan review doc | https://claude.ai/artifact/XRbXnA3USEdg7H7sZFfYgR (the `docs/` files are the source of truth) |

## Stack (approved 2026-11-23 — see docs/TECH_STACK.md, ADR 0001)

- Backend: Python 3.13, FastAPI, SQLAlchemy 2 async, Celery + Redis, PostgreSQL + TimescaleDB + pgvector
- AI/ML: LightGBM, scikit-learn, vectorbt, TA-Lib, Claude API (Haiku 5.5 bulk news, Opus 5.5 final reasoning)
- Web: Next.js + Tailwind + shadcn/ui + lightweight-charts. Mobile: Expo (later phase)
- Monorepo: `apps/api`, `apps/web`, `apps/mobile`, `packages/*`; uv (Python) + pnpm workspaces (TS)
- Tooling: Ruff, mypy, pytest · Biome, TypeScript, Vitest · GitHub Actions

## Commands

From the repo root, `pnpm <task>` runs every package's task through Turborepo, the
Python backend included (`apps/api/package.json` wraps the uv commands).

| Task | Everything (root) | Python only (in `apps/api`) |
| --- | --- | --- |
| Install | `pnpm install` + `uv sync` (in `apps/api`) | `uv sync` |
| Lint | `pnpm lint` | `uv run ruff check . && uv run ruff format --check .` |
| Format | `pnpm format` | `uv run ruff format . && uv run ruff check --fix .` |
| Typecheck | `pnpm typecheck` | `uv run mypy` (strict) |
| Test | `pnpm test` | `uv run pytest` (coverage printed; warnings fail) |
| Dev DB + Redis | `pnpm infra:up` / `infra:down` / `infra:logs` / `infra:ps` | Postgres 17 + TimescaleDB + pgvector on 127.0.0.1:5432, Redis on :6379 |
| Migrate DB | `pnpm db:migrate` | `uv run alembic upgrade head` · `downgrade -1` · `revision --autogenerate -m "..."` (import new models in `app/data/models/__init__.py`) |
| Workers | `pnpm worker` / `pnpm beat` | `uv run celery -A app.worker.celery_app worker` / `beat` (needs `pnpm infra:up`) |
| Run API | `pnpm dev` | `uv run uvicorn app.main:create_app --factory --reload` → http://localhost:8000/docs |

Python config lives in `apps/api/pyproject.toml` (Ruff rules, mypy strict + pydantic plugin,
pytest with `asyncio_mode = auto`, `integration` marker for tests needing Docker).

## Workflow rules

1. Branches (owner's rule, 2026-11-23): `develop` is the integration branch and GitHub's
   default; `main` holds released code only. Never commit or push directly to `main` or
   `develop`. Each phase uses branch `phase-<n>-<slug>`, cut from the latest `develop`, and
   its PR targets `develop`. A release is a PR from `develop` → `main` that the owner merges.
   The only direct commit ever is the first "chore: project setup" commit on `develop`;
   `main` is created pointing at that same commit, with nothing committed to it.
2. One ticket = one task. On start: Status = In Progress, Locked by = `laptop` or `cloud`.
3. Write/update tests with every ticket. Run lint + typecheck + tests before committing.
4. Commit message `AITP-<n>: <summary>`. Push after every ticket. Put the commit hash in the
   ticket, tick its acceptance criteria, Status = Done, clear Locked by.
5. After 2 failed attempts or any unclear requirement: comment on the ticket, set Blocked or
   Needs Decision, move to the next ticket.
6. After each ticket: update `docs/PROGRESS.md` (done, next, open questions, session log) and
   the CHANGELOG.md Unreleased section, in that ticket's commit.
7. Big technical choices → new ADR in `docs/decisions/`.
8. Scope changes: update `docs/PLAN.md` first, then Notion. PLAN.md = source of truth for
   scope; Notion = source of truth for status.
9. Phase completion: all tickets Done → merge the latest `origin/develop` into the phase
   branch (never rebase a pushed branch; that would need a force push) → full checks →
   self-review the whole diff with a fresh subagent and fix issues → push → `gh pr create
   --base develop` with the PR template → tickets and phase row to In Review with PR URL →
   give owner the link.
10. Wait for CI to pass; if it fails, fix it before saying the PR is ready.
11. NEVER merge PRs, force-push, or push to `main` or `develop` directly (GitHub branch
    protection also blocks it). Never read `.env` files or use production credentials; read
    `.env.example` with `git show HEAD:.env.example`. No live-trading code path may bypass
    the risk engine.

Phase size: 5–8 tickets, roughly ≤600 changed lines per PR; split bigger phases (3a/3b).

## Before ending a session

Update `docs/PROGRESS.md`: what was done, what's next, open questions, a session-log row
(date + laptop/cloud). This file is what the next session starts from.

## Docs map

- `docs/SETUP_PLAN.md` — full project-setup checklist (Steps 0–9) and progress on it
- `docs/ARCHITECTURE.md` — system design, data flow, folder layout, conventions
- `docs/TECH_STACK.md` — every package and why
- `docs/COSTS.md` — monthly cost estimates by stage
- `docs/RISKS_AND_COMPLIANCE.md` — risks, India compliance notes, owner decisions
- `docs/PLAN.md` — phases and tickets (filled by /plan-project)
- `docs/decisions/` — ADRs (`0000-template.md`)
- `docs/PROGRESS.md` — current state; updated every session
