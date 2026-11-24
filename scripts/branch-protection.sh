#!/usr/bin/env bash
# Applies the repo's branch protection to main and develop. Safe to re-run.
# Needs: gh signed in as a repo admin. Usage: bash scripts/branch-protection.sh [owner/repo]
#
# Rules: changes only through a pull request; every CI job must pass and the branch must be up to
# date; conversations resolved; no force pushes or deletions; admins are not exempt.
# (0 required approvals: the owner is the only reviewer, and GitHub does not let you approve your own PR.)
set -euo pipefail

REPO="${1:-Vivek-2306/ai-trading-platform}"
CHECKS='["API (Python)","Web (TypeScript)","Packages (import smoke)","Secret scan (gitleaks)"]'

for branch in main develop; do
  gh api -X PUT "repos/${REPO}/branches/${branch}/protection" --input - >/dev/null <<JSON
{
  "required_status_checks": { "strict": true, "contexts": ${CHECKS} },
  "enforce_admins": true,
  "required_pull_request_reviews": { "required_approving_review_count": 0 },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
JSON
  echo "protected: ${branch}"
done
