-- Capitok schema reference snapshot
--
-- Primary schema evolution should happen through Alembic migrations in migrations/.
-- This file is kept as a readable snapshot and must remain aligned with the migration history.
--
-- Design notes:
-- 1. raw_chat_logs is append-only and stores the immutable source of truth.
-- 2. refined_memories stores tenant-scoped derived recall records rebuilt from raw data when needed.
-- 3. tenant_id and principal_id are mandatory for every row to enforce isolation.
-- 4. embedding_version is required so downstream embeddings can be regenerated later.
-- 5. search_vector is derived from text for stable full-text search behavior.

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS raw_chat_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id text NOT NULL,
    principal_id text NOT NULL,
    session_id text NOT NULL,
    user_id text NOT NULL,
    agent_id text NOT NULL,
    source text NOT NULL,
    content jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE raw_chat_logs IS 'Append-only raw interaction log. Acts as the source-of-truth archive layer.';
COMMENT ON COLUMN raw_chat_logs.tenant_id IS 'Server-derived tenant boundary. Never trust client-provided isolation.';
COMMENT ON COLUMN raw_chat_logs.principal_id IS 'Server-derived principal or user context for scoped access.';
COMMENT ON COLUMN raw_chat_logs.content IS 'Raw JSON payload from the agent/runtime integration.';

CREATE INDEX IF NOT EXISTS idx_raw_chat_logs_tenant_principal_created
    ON raw_chat_logs (tenant_id, principal_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_raw_chat_logs_session
    ON raw_chat_logs (session_id);

CREATE TABLE IF NOT EXISTS refined_memories (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id text NOT NULL,
    principal_id text NOT NULL,
    session_id text NOT NULL,
    user_id text NOT NULL,
    text text NOT NULL,
    embedding vector(1536),
    embedding_version text NOT NULL,
    search_vector tsvector GENERATED ALWAYS AS (to_tsvector('simple', coalesce(text, ''))) STORED,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE refined_memories IS 'Derived searchable records generated from the raw archive for recall workflows.';
COMMENT ON COLUMN refined_memories.embedding_version IS 'Tracks which downstream embedding model/version produced this vector.';
COMMENT ON COLUMN refined_memories.search_vector IS 'Generated tsvector column for baseline keyword recall over derived records.';

CREATE INDEX IF NOT EXISTS idx_refined_memories_tenant_principal_created
    ON refined_memories (tenant_id, principal_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_refined_memories_search_vector
    ON refined_memories USING GIN (search_vector);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = current_schema()
          AND indexname = 'idx_refined_memories_embedding_hnsw'
    ) THEN
        EXECUTE 'CREATE INDEX idx_refined_memories_embedding_hnsw ON refined_memories USING hnsw (embedding vector_cosine_ops)';
    END IF;
END $$;

-- Operational note:
-- HNSW index creation may fail if the pgvector extension version does not support it.
-- If that happens in a given environment, fall back to a GIN/IVFFLAT-based strategy
-- or create the ANN index in a later migration after validating extension support.
