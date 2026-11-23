---
description: Summarise a phase - Notion tickets by status, branch commits, PR and CI, blockers
argument-hint: <phase number, optional; defaults to the current phase>
---

Report status for phase $ARGUMENTS (if empty, use the current phase from `docs/PROGRESS.md`).

Read-only: change nothing.

1. Notion: this phase's tickets grouped by Status (ID, title, Locked by). Phase row Status and PR.
2. Git: `git log --oneline origin/develop..origin/<phase branch>`.
3. PR, if any: `gh pr view <branch> --json url,state,reviewDecision,mergeable` and `gh pr checks <branch>`.
4. Blockers: tickets in Blocked or Needs Decision, with their latest comment.

Answer in a short table plus a one-line "next step".
