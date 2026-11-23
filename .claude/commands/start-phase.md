---
description: Prepare a phase - branch from develop, Notion tickets, progress update - then wait for "go"
argument-hint: <phase number>
---

Start phase $ARGUMENTS.

Follow the rules in CLAUDE.md (Notion IDs and ticket properties are listed there).

1. `git fetch` and `git checkout develop && git pull`. Stop if the working tree isn't clean.
2. Read the phase in `docs/PLAN.md`. Stop and ask if it's missing or not approved.
3. Create branch `phase-<n>-<slug>` from `develop` (slug from the phase name). Don't push yet.
4. In the Tickets DB, check which of the phase's tasks already have tickets. Create one ticket
   per missing task: Title, Status = To Do, Phase, Phase page (relation), Type, Priority,
   Branch, and the acceptance criteria as a `- [ ]` checklist in the body.
5. Make sure the phase row in the Phases DB exists with Goal and Branch; Status = Planned.
6. Update `docs/PROGRESS.md`: current phase, the ticket list, Last updated (date + laptop/cloud).
7. Show the owner the ticket list (ID, title, type, priority) and wait for "go".
