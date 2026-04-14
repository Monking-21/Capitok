#!/usr/bin/env bash
set -euo pipefail

DB_URL="${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/capitok}"
OUTPUT_FILE="${1:-memory_backup.sql}"

# Back up both the source-of-truth raw archive and the derived recall table.
pg_dump "$DB_URL" -t raw_chat_logs -t refined_memories > "$OUTPUT_FILE"
echo "Backup completed: $OUTPUT_FILE"
