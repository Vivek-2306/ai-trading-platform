---
description: Fix the owner's review comments on a PR, push, and reply to each comment
argument-hint: <PR number>
---

Address review feedback on PR #$ARGUMENTS.

Follow the rules in CLAUDE.md.

1. Read everything: `gh pr view $ARGUMENTS --comments`, review comments with
   `gh api repos/{owner}/{repo}/pulls/$ARGUMENTS/comments`, and reviews with
   `gh api repos/{owner}/{repo}/pulls/$ARGUMENTS/reviews`.
2. Check out the PR branch and pull.
3. List each comment with your planned response (fix, or explain why not). If a comment
   asks for something unclear or out of scope, ask the owner before acting.
4. Make the fixes, with tests where relevant. Run lint, typecheck and tests.
5. Commit as `<ticket ID>: address review - <summary>` and push with
   `git push origin <branch>` (no force-push).
6. Reply to each comment (`gh api` POST to the comment's replies endpoint, or `gh pr comment`
   for general ones) saying what changed and in which commit.
7. Wait for CI to be green, then summarise for the owner what changed and what was not changed.
