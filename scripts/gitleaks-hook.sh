#!/usr/bin/env bash
# Pre-commit: scan staged changes for secrets. If gitleaks is not installed, warn and continue
# (CI scans the full history anyway). Install: brew install gitleaks
if ! command -v gitleaks >/dev/null 2>&1; then
  echo "gitleaks is not installed, skipping the local secret scan (CI will still scan)"
  exit 0
fi
exec gitleaks protect --staged --redact --no-banner
