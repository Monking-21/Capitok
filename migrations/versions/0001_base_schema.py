"""base schema

Revision ID: 0001_base_schema
Revises:
Create Date: 2026-04-12
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_base_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute(
        """
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
        )
        """
    )

    op.execute(
        """
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
        )
        """
    )

    op.execute(
        """
        COMMENT ON TABLE raw_chat_logs IS 'Append-only raw interaction log. Acts as the source-of-truth archive layer.'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN raw_chat_logs.tenant_id IS 'Server-derived tenant boundary. Never trust client-provided isolation.'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN raw_chat_logs.principal_id IS 'Server-derived principal or user context for scoped access.'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN raw_chat_logs.content IS 'Raw JSON payload from the agent/runtime integration.'
        """
    )
    op.execute(
        """
        COMMENT ON TABLE refined_memories IS 'Derived searchable records generated from the raw archive for recall workflows.'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN refined_memories.embedding_version IS 'Tracks which downstream embedding model/version produced this vector.'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN refined_memories.search_vector IS 'Generated tsvector column for baseline keyword recall over derived records.'
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS refined_memories")
    op.execute("DROP TABLE IF EXISTS raw_chat_logs")
