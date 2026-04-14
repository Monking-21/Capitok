from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator

from psycopg import Connection, connect
from psycopg.rows import dict_row
from psycopg.types.json import Json

from capitok.config import get_settings


def _normalize_psycopg_dsn(database_url: str) -> str:
    # Accept SQLAlchemy-style driver URLs while using psycopg directly.
    if database_url.startswith("postgresql+psycopg://"):
        return database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    return database_url


@contextmanager
def get_db() -> Generator[Connection, None, None]:
    settings = get_settings()
    conn = connect(_normalize_psycopg_dsn(settings.database_url), row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def insert_raw_chat_log(
    tenant_id: str,
    principal_id: str,
    session_id: str,
    user_id: str,
    agent_id: str,
    source: str,
    content: dict,
) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO raw_chat_logs
                (tenant_id, principal_id, session_id, user_id, agent_id, source, content)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (tenant_id, principal_id, session_id, user_id, agent_id, source, Json(content)),
            )


def insert_refined_memory(
    tenant_id: str,
    principal_id: str,
    session_id: str,
    user_id: str,
    text: str,
    embedding_version: str,
) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO refined_memories
                (tenant_id, principal_id, session_id, user_id, text, embedding_version, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    tenant_id,
                    principal_id,
                    session_id,
                    user_id,
                    text,
                    embedding_version,
                    datetime.now(timezone.utc),
                    datetime.now(timezone.utc),
                ),
            )


def search_refined_memories(
    tenant_id: str,
    principal_id: str,
    query: str,
    top_k: int,
) -> list[dict]:
    with get_db() as conn:
        with conn.cursor() as cur:
            # MVP keeps ranking logic simple and deterministic using PostgreSQL FTS.
            cur.execute(
                """
                SELECT
                    id::text AS id,
                    session_id,
                    user_id,
                    text,
                    ts_rank(search_vector, websearch_to_tsquery('simple', %s)) AS score,
                    created_at
                FROM refined_memories
                WHERE tenant_id = %s
                  AND principal_id = %s
                  AND search_vector @@ websearch_to_tsquery('simple', %s)
                ORDER BY score DESC, created_at DESC
                LIMIT %s
                """,
                (query, tenant_id, principal_id, query, top_k),
            )
            return list(cur.fetchall())
