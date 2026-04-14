#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <backup-file.sql>"
  exit 1
fi

DB_URL="${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/capitok}"
BACKUP_FILE="$1"

psql "$DB_URL" < "$BACKUP_FILE"
echo "Restore completed from: $BACKUP_FILE"
