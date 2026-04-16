from contextlib import contextmanager
import copy
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


def transcript_snapshot_exists(
    tenant_id: str,
    principal_id: str,
    session_id: str,
    source: str,
    transcript_sha256: str,
) -> bool:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM transcript_snapshots
                    WHERE tenant_id = %s
                      AND principal_id = %s
                      AND session_id = %s
                      AND source = %s
                      AND transcript_sha256 = %s
                ) AS exists
                """,
                (tenant_id, principal_id, session_id, source, transcript_sha256),
            )
            row = cur.fetchone()
            return bool(row["exists"]) if row else False


def _fetch_raw_chat_logs(
    tenant_id: str,
    principal_id: str,
    source: str | None = None,
    session_id: str | None = None,
    limit: int | None = None,
    descending: bool = False,
) -> list[dict]:
    clauses = ["tenant_id = %s", "principal_id = %s"]
    params: list[object] = [tenant_id, principal_id]

    if source is not None:
        clauses.append("source = %s")
        params.append(source)
    if session_id is not None:
        clauses.append("session_id = %s")
        params.append(session_id)

    order = "DESC" if descending else "ASC"
    query = f"""
        SELECT
            id::text AS id,
            session_id,
            source,
            content,
            created_at
        FROM raw_chat_logs
        WHERE {" AND ".join(clauses)}
        ORDER BY created_at {order}, id {order}
    """
    if limit is not None:
        query += " LIMIT %s"
        params.append(limit)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            return list(cur.fetchall())


def _extract_payload(row: dict, key: str) -> str:
    content = row.get("content") or {}
    if isinstance(content, dict):
        value = content.get(key, "")
        return "" if value is None else str(value)
    return ""


def _extract_metadata(row: dict) -> dict:
    content = row.get("content") or {}
    if isinstance(content, dict):
        metadata = content.get("metadata", {})
        if isinstance(metadata, dict):
            return copy.deepcopy(metadata)
    return {}


def _truncate_preview(text: str, max_length: int = 80) -> str:
    if len(text) <= max_length:
        return text
    if max_length <= 3:
        return text[:max_length]
    return text[: max_length - 3].rstrip() + "..."


def list_recent_sessions(
    tenant_id: str,
    principal_id: str,
    limit: int,
    source: str | None = None,
) -> list[dict]:
    clauses = ["base.tenant_id = %s", "base.principal_id = %s"]
    params: list[object] = [tenant_id, principal_id]

    if source is not None:
        clauses.append("base.source = %s")
        params.append(source)

    query = f"""
        SELECT
            base.session_id,
            base.source,
            MIN(base.created_at) AS started_at,
            MAX(base.created_at) AS updated_at,
            COUNT(*)::int AS record_count,
            (
                SELECT COALESCE(content->>'input', '')
                FROM raw_chat_logs first_log
                WHERE first_log.tenant_id = base.tenant_id
                  AND first_log.principal_id = base.principal_id
                  AND first_log.session_id = base.session_id
                  AND first_log.source = base.source
                  AND COALESCE(content->>'input', '') <> ''
                ORDER BY first_log.created_at ASC, first_log.id ASC
                LIMIT 1
            ) AS preview
        FROM raw_chat_logs base
        WHERE {" AND ".join(clauses)}
        GROUP BY base.tenant_id, base.principal_id, base.session_id, base.source
        ORDER BY updated_at DESC, started_at DESC, base.session_id ASC, base.source ASC
        LIMIT %s
    """
    params.append(limit)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = list(cur.fetchall())

    return [
        {
            "session_id": row["session_id"],
            "source": row["source"],
            "preview": _truncate_preview(str(row.get("preview", ""))),
            "started_at": row["started_at"],
            "updated_at": row["updated_at"],
            "record_count": row["record_count"],
        }
        for row in rows
    ]


def list_recent_records(
    tenant_id: str,
    principal_id: str,
    limit: int,
    source: str | None = None,
) -> list[dict]:
    rows = _fetch_raw_chat_logs(
        tenant_id=tenant_id,
        principal_id=principal_id,
        source=source,
        limit=limit,
        descending=True,
    )
    return [
        {
            "id": row["id"],
            "session_id": row["session_id"],
            "source": row["source"],
            "created_at": row["created_at"],
            "input": _extract_payload(row, "input"),
            "output": _extract_payload(row, "output"),
        }
        for row in rows
    ]


def get_session_detail(
    tenant_id: str,
    principal_id: str,
    session_id: str,
    source: str | None = None,
) -> dict | None:
    rows = _fetch_raw_chat_logs(
        tenant_id=tenant_id,
        principal_id=principal_id,
        session_id=session_id,
        source=source,
        descending=False,
    )
    if not rows:
        return None

    if source is None:
        sources = {row["source"] for row in rows}
        if len(sources) > 1:
            raise ValueError("Multiple sources share this session_id; pass source")

    return {
        "session_id": session_id,
        "source": rows[0]["source"],
        "started_at": rows[0]["created_at"],
        "updated_at": rows[-1]["created_at"],
        "record_count": len(rows),
        "items": [
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "input": _extract_payload(row, "input"),
                "output": _extract_payload(row, "output"),
                "metadata": _extract_metadata(row),
            }
            for row in rows
        ],
    }
