"""refined memory indexes

Revision ID: 0002_refined_memory_indexes
Revises: 0001_base_schema
Create Date: 2026-04-12
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_refined_memory_indexes"
down_revision = "0001_base_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_raw_chat_logs_tenant_principal_created
            ON raw_chat_logs (tenant_id, principal_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_raw_chat_logs_session
            ON raw_chat_logs (session_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_refined_memories_tenant_principal_created
            ON refined_memories (tenant_id, principal_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_refined_memories_search_vector
            ON refined_memories USING GIN (search_vector)
        """
    )
    op.execute(
        """
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
        END $$
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_refined_memories_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS idx_refined_memories_search_vector")
    op.execute("DROP INDEX IF EXISTS idx_refined_memories_tenant_principal_created")
    op.execute("DROP INDEX IF EXISTS idx_raw_chat_logs_session")
    op.execute("DROP INDEX IF EXISTS idx_raw_chat_logs_tenant_principal_created")
