#!/usr/bin/env bash
# PostToolUse hook: format the file Claude just wrote or edited.
# - .py            -> Ruff (from apps/api's uv environment)
# - .ts/.tsx/.js/.jsx/.json/.jsonc -> Biome (from the pnpm workspace)
# Skips quietly when the formatter isn't installed yet. Never blocks Claude.

set -u
root="$(cd "$(dirname "$0")/../.." && pwd)"

file="$(jq -r '.tool_response.filePath // .tool_input.file_path // empty' 2>/dev/null)"
[ -n "$file" ] && [ -f "$file" ] || exit 0

case "$file" in
  *.py)
    if [ -f "$root/apps/api/pyproject.toml" ] && command -v uv >/dev/null 2>&1; then
      uv run --quiet --no-sync --project "$root/apps/api" ruff format --quiet "$file" >/dev/null 2>&1
    fi
    ;;
  *.ts|*.tsx|*.js|*.jsx|*.json|*.jsonc)
    biome="$root/node_modules/.bin/biome"
    if [ -x "$biome" ]; then
      "$biome" format --write "$file" >/dev/null 2>&1
    fi
    ;;
esac

exit 0
