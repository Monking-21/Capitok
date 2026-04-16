#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv was not found in PATH." >&2
  echo "Install uv first, then rerun this script." >&2
  exit 1
fi

cd "$repo_root"
exec uv run python integrations/codex/install.py
