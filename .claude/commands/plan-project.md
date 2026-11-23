---
description: Interview the owner about a feature idea and write phased tasks into docs/PLAN.md
argument-hint: <idea or area to plan>
---

Plan new work for: $ARGUMENTS

Follow the rules in CLAUDE.md. Do not write application code.

1. Read `docs/PROGRESS.md`, `docs/PLAN.md`, `docs/ARCHITECTURE.md` and the open questions in
   `docs/RISKS_AND_COMPLIANCE.md`.
2. Interview the owner: ask only the questions whose answers change the plan, all in one
   message. Record each answer in the right doc.
3. Propose phases. Each phase: a goal, 5–8 small tasks, each with Type, Priority and 2–5
   testable acceptance criteria, and an "Out of scope" line. Keep each phase to roughly
   ≤600 changed lines; split bigger ones (3a/3b).
4. Show the proposal and wait for the owner's approval. Revise until approved.
5. Write the approved phases into `docs/PLAN.md` (keep existing phases intact) and add an ADR
   in `docs/decisions/` for any big technical choice.
6. Update `docs/PROGRESS.md` (Next up). Tickets are created later by `/start-phase`.
