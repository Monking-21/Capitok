#!/usr/bin/env bash
set -euo pipefail

# Keep schema snapshot in sync with migration-applied database state.
# Default targets local dev database; override via DATABASE_URL.

DB_URL="${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/capitok}"
OUTPUT_FILE="${1:-sql/schema.sql}"
TMP_FILE="${OUTPUT_FILE}.tmp"

pg_dump "$DB_URL" \
  --schema-only \
  --no-owner \
  --no-privileges \
  --schema=public \
  > "$TMP_FILE"

# Prepend a short generated-file notice.
{
  echo "-- GENERATED FILE: do not edit manually"
  echo "-- Source of truth: Alembic migrations in migrations/"
  echo "-- Regenerate with: ./scripts/dump-schema.sh"
  echo
  cat "$TMP_FILE"
} > "$OUTPUT_FILE"

rm -f "$TMP_FILE"
echo "Schema snapshot updated: $OUTPUT_FILE"
