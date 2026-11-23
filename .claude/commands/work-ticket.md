---
description: Implement one Notion ticket end to end on the current phase branch
argument-hint: <ticket ID, e.g. AITP-12>
---

Work ticket $ARGUMENTS.

Follow the rules in CLAUDE.md.

1. Fetch the ticket from Notion. Confirm you're on its Branch (cut from `develop`).
2. If Status is In Progress with a different Locked by than this environment, stop and ask.
3. Set Status = In Progress and Locked by = `laptop` or `cloud` (this environment).
4. Implement exactly what the acceptance criteria ask. Write or update tests.
5. Run lint, typecheck and tests (commands in CLAUDE.md). Fix failures.
6. If you're stuck after 2 attempts, or a requirement is unclear: comment on the ticket,
   set Status = Blocked or Needs Decision, clear Locked by, tell the owner, and stop.
7. Commit as `<ID>: <summary>` and push the branch (never to `develop` or `main`).
8. In Notion: tick each met criterion, set Commit = short hash, Status = Done, clear Locked by.
   Add a short note to the ticket for anything a reviewer should know.
9. Update `docs/PROGRESS.md` and the Unreleased section of `CHANGELOG.md`.
