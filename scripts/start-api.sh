#!/usr/bin/env bash
set -euo pipefail

MODE="${1:---dev}"

./scripts/wait-for-db.sh

if ! command -v uv >/dev/null 2>&1; then
  pip install --no-cache-dir uv
fi

if [[ "$MODE" == "--dev" ]]; then
  uv sync
else
  uv sync --no-dev --no-editable
fi

uv run alembic -c alembic.ini upgrade head
exec uv run uvicorn capitok.main:app --host 0.0.0.0 --port 8000
