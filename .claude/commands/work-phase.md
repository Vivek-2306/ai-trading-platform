---
description: Work every To Do ticket of a phase, then open the phase PR into develop
argument-hint: <phase number>
---

Work phase $ARGUMENTS.

Follow the rules in CLAUDE.md.

1. Check out the phase branch and `git pull`. Set the phase row Status = In Progress.
2. Query the Tickets DB for this phase's To Do tickets, in ID order.
3. For each ticket, follow `/work-ticket` exactly. A fresh subagent per ticket is fine when
   the ticket is self-contained; the main session still updates Notion and PROGRESS.md.
   Blocked or Needs Decision tickets are skipped; carry on with the rest.
4. When every ticket is Done (or the owner agrees to defer the blocked ones):
   1. `git fetch` and rebase on the latest `origin/develop`; resolve conflicts.
   2. Run the full checks: lint, typecheck, tests.
   3. Review the whole phase diff (`git diff origin/develop...HEAD`) with a fresh subagent;
      fix what it finds and re-run the checks.
   4. Push the branch (a plain push; force-push is not allowed. If a rebase needs one, ask).
   5. `gh pr create --base develop` using `.github/pull_request_template.md`: list every
      ticket with its Notion link, what changed, how it was tested, risky areas first.
   6. Set the phase's tickets to In Review with the PR URL; set the phase row Status =
      In Review and PR = URL.
   7. Update CHANGELOG.md (Unreleased) and `docs/PROGRESS.md`.
5. Wait for CI (`gh pr checks --watch`). If it fails, fix, push, and wait again.
6. Only when CI is green, give the owner the PR link. Never merge it.
