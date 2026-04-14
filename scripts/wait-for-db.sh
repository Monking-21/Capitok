#!/usr/bin/env bash
set -euo pipefail

host="${DB_HOST:-db}"
port="${DB_PORT:-5432}"

for _ in $(seq 1 60); do
  if python - <<PY
import socket
try:
    with socket.create_connection(("${host}", ${port}), timeout=1):
        pass
except OSError:
    raise SystemExit(1)
PY
  then
    exit 0
  fi
  sleep 1
done

echo "database did not become ready"
exit 1
