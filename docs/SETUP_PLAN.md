# Project setup plan

The owner's setup spec, saved so any session can continue it. Tick steps as they finish.
Rule for the whole setup: no application code; stop and ask whenever the owner's input or a
manual action is needed.

**Update 2026-11-23:** Steps 2–8 are now delivered as setup Phases 1–6 in `docs/PLAN.md`
(Notion tickets AITP-1 … AITP-35, one PR per phase). Claude implements; the owner reviews
tickets and PRs and merges. Steps below are ticked as their phase merges.

Done so far: `git init -b main`, GitHub repo created (public) with remote `origin`;
Step 3 Notion tracker complete (project page, Phases DB, Tickets DB with Board view,
Decisions page).

Tools: Claude Code (laptop + Claude mobile app / cloud sessions), Notion (Jira-style board),
GitHub (owner reviews and merges PRs).

## Step 0 — Owner answers ✅

- Name: AI-Powered Trading Platform (description in `CLAUDE.md`)
- Stack: Claude proposes → see `docs/TECH_STACK.md` (awaiting approval)
- Repo: `ai-trading-platform`, public
- Notion parent page: "Projects"
- Ticket prefix: `AITP`

## Step 1 — Prerequisites ✅

- [x] `git --version`, `gh auth status`, node, pnpm, python
- [x] Notion MCP connected; parent page found
- [x] uv 0.13.9 (installed 2026-11-23); Docker 28.2.2

## Step 2 — Repo and GitHub

- [ ] `git init -b main`; `gh repo create Vivek-2306/ai-trading-platform --public`; set remote
- [ ] Scaffold minimal monorepo: `apps/api` (uv, Ruff, mypy, pytest, one passing test),
      `apps/web` (Next.js, Biome, TypeScript, Vitest, one passing test), pnpm workspace
- [ ] Working commands for install, lint, typecheck, test → write into `CLAUDE.md`

## Step 3 — Notion tracker

Under "Projects": page "AI Trading Platform" containing database "AI Trading Platform Tickets":

- Title (title); ID (unique ID with prefix AITP if supported, else text AITP-<n>)
- Status: To Do, In Progress, Blocked, Needs Decision, In Review, Done
- Phase (select): Phase 1 … Phase 6; Type: Feature, Bug, Chore, Docs, Test
- Priority: High, Medium, Low; Branch (text), Commit (text), PR (url)
- Locked by (select): laptop, cloud
- Acceptance criteria = to-do checklist in the page body

Also a page "AI Trading Platform Decisions". Record DB URL + ID in `CLAUDE.md`.
If a Board view can't be created through the API, tell the owner.

- [ ] Page, database, Decisions page created; IDs recorded

## Step 4 — Project memory files

Already created early (update, don't recreate): `CLAUDE.md`, `docs/PROGRESS.md`,
`docs/PLAN.md`, `docs/ARCHITECTURE.md`, `docs/decisions/0000-template.md`.

- [ ] `CHANGELOG.md` (Keep a Changelog, Unreleased section)
- [ ] `.env.example`; `.gitignore` for Python + Node (ignore `.env*` except `.env.example`)
- [ ] Fill real commands and links into `CLAUDE.md` (keep it under ~150 lines)

## Step 5 — Slash commands (`.claude/commands/`)

- [ ] `plan-project.md` — interview owner about $ARGUMENTS, propose phases (5–8 small tasks,
      each with acceptance criteria), write `docs/PLAN.md`, wait for approval
- [ ] `start-phase.md` — phase $ARGUMENTS: pull main, create branch, one Notion ticket per task
      (To Do, Phase, Type, Priority, Branch, criteria), update PROGRESS.md, show list, wait for "go"
- [ ] `work-phase.md` — work To Do tickets of phase $ARGUMENTS one at a time (fresh subagent per
      ticket where helpful), then phase-completion steps
- [ ] `work-ticket.md` — one ticket ($ARGUMENTS = ticket ID)
- [ ] `phase-status.md` — Notion summary by status, branch commits, PR + CI (`gh pr view`,
      `gh pr checks`), blockers
- [ ] `handoff.md` — update PROGRESS.md, push, release Locked by, short summary for another device
- [ ] `address-review.md` — read PR $ARGUMENTS comments (`gh pr view --comments`, `gh api`),
      fix, push, reply to each, summarise
- [ ] `release-phase.md` — after owner merges: pull main, tag `v0.<n>.0-phase-<n>`, move
      CHANGELOG Unreleased to that version, tickets Done, update PROGRESS.md

## Step 6 — `.claude/settings.json`

- [ ] allow: git (not push to main / force), `gh pr create/view/checks/comment`, read-only
      `gh api`, install/lint/test/typecheck commands, `mcp__notion`
- [ ] deny: `gh pr merge`, `git push --force`, `git push -f`, `git push origin main`,
      `Read(.env*)` (allow `.env.example`), `Read(**/secrets/**)`, `rm -rf`
- [ ] PostToolUse hook: run Ruff format / Biome format on edited files

## Step 7 — GitHub automation

- [ ] `.github/workflows/ci.yml`: on pull_request + push to main → install, lint, typecheck,
      test; dependency caching; fast
- [ ] `.github/pull_request_template.md`: Summary, Tickets (Notion links), What changed,
      How it was tested, Risky areas to review first, Screenshots (UI)
- [ ] Protect main via `gh api` (require PR, require CI, block force push). If refused,
      don't retry; tell owner the options

## Step 8 — Commit and verify

- [ ] Initial commit "chore: project setup" on `develop` (the only direct commit) and push;
      `main` created at the same commit; `develop` set as default branch.
      (Owner rule 2026-11-23: phase PRs go into `develop`; releases go `develop` → `main`.)
- [ ] Smoke test: Notion ticket "AITP: Setup smoke test" in Phase 1, To Do → In Progress →
      Done, then archive. Confirm CI green on GitHub
- [ ] List `.claude/commands` and confirm each loads

## Step 9 — Final report to owner

1. What was created (links: repo, Notion DB, CI run)
2. What failed or was skipped, and why
3. Owner's manual checklist: Notion Board view (group by Status) + "Blocked" view; cloud
   environment at claude.ai/code (setup script to install deps, dev/test env vars only,
   connect Notion); notifications (Claude app, GitHub app, Notion watch DB); branch
   protection if it failed
4. How to start: `/plan-project <idea>` → `/start-phase 1` → `/work-phase 1`
