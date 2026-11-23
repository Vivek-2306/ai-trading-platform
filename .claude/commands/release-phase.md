---
description: After the owner merges a phase PR (into develop) or a release PR (develop to main), close it out
argument-hint: <phase number, or "release vX.Y.Z">
---

Close out: $ARGUMENTS

Follow the rules in CLAUDE.md. Never push directly to `develop` or `main`.

**A phase PR was merged into `develop`:**

1. `git checkout develop && git pull`. Confirm the phase PR shows as merged (`gh pr view`).
2. In Notion: set the phase's tickets from In Review to Done; set the phase row Status = Done.
3. Delete the merged local branch.
4. Update `docs/PROGRESS.md` (phase done, next phase) on the next phase branch, or tell the
   owner if there's no next phase branch yet.

**A release PR was merged from `develop` into `main` (e.g. "release v0.1.0"):**

1. `git checkout main && git pull`. Confirm the release PR is merged.
2. Create the tag on `main` (e.g. `git tag -a v0.1.0 -m "v0.1.0"`) and push only the tag
   (`git push origin v0.1.0`).
3. Fill the phase rows' Release tag in Notion.
4. On a new branch from `develop`, move the CHANGELOG "Unreleased" entries under the new
   version heading with today's date; update `docs/PROGRESS.md`; open a small PR into `develop`.
