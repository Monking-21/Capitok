from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query

from capitok.config import get_settings
from capitok.db import (
    get_session_detail,
    insert_raw_chat_log,
    list_recent_records,
    list_recent_sessions,
    search_refined_memories,
    transcript_snapshot_exists,
)
from capitok.queue.inprocess import InProcessQueueAdapter
from capitok.queue.interface import RefineTask
from capitok.schemas import (
    IngestRequest,
    IngestResponse,
    SearchResponse,
    SearchResult,
    SessionDetailResponse,
    SessionListItem,
    SessionListResponse,
    SessionRecordListItem,
    TranscriptSnapshotExistsResponse,
)
from capitok.security import IdentityContext, require_scope

settings = get_settings()
app = FastAPI(title=settings.app_name)
queue_adapter = InProcessQueueAdapter()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "env": settings.app_env}


@app.post("/v1/ingest", response_model=IngestResponse)
async def archive_interaction(
    payload: IngestRequest,
    identity: IdentityContext = Depends(require_scope("ingest")),
) -> IngestResponse:
    content = {
        "input": payload.input,
        "output": payload.output,
        "metadata": payload.metadata,
    }

    agent_id = str(payload.metadata.get("agent", "unknown"))

    insert_raw_chat_log(
        tenant_id=identity.tenant_id,
        principal_id=identity.principal_id,
        session_id=payload.session_id,
        user_id=payload.user_id,
        agent_id=agent_id,
        source=payload.source,
        content=content,
    )

    text = f"{payload.input}\n{payload.output}".strip()
    await queue_adapter.enqueue_refine_task(
        RefineTask(
            tenant_id=identity.tenant_id,
            principal_id=identity.principal_id,
            session_id=payload.session_id,
            user_id=payload.user_id,
            text=text,
            embedding_version="mvp-text-v1",
        )
    )

    return IngestResponse(status="queued", message="Raw interaction archived; derived recall indexing queued")


@app.get("/v1/search", response_model=SearchResponse)
def search_recall_records(
    query: str = Query(min_length=1),
    top_k: int = Query(default=10, ge=1, le=50),
    identity: IdentityContext = Depends(require_scope("search")),
) -> SearchResponse:
    rows = search_refined_memories(
        tenant_id=identity.tenant_id,
        principal_id=identity.principal_id,
        query=query,
        top_k=top_k,
    )
    return SearchResponse(items=[SearchResult(**row) for row in rows])


@app.get("/v1/transcript-snapshots/exists", response_model=TranscriptSnapshotExistsResponse)
def transcript_snapshot_exists_route(
    session_id: str = Query(min_length=1),
    source: str = Query(min_length=1),
    transcript_sha256: str = Query(min_length=1),
    identity: IdentityContext = Depends(require_scope("search")),
) -> TranscriptSnapshotExistsResponse:
    exists = transcript_snapshot_exists(
        tenant_id=identity.tenant_id,
        principal_id=identity.principal_id,
        session_id=session_id,
        source=source,
        transcript_sha256=transcript_sha256,
    )
    return TranscriptSnapshotExistsResponse(exists=exists)


@app.get("/v1/sessions", response_model=SessionListResponse)
def list_sessions(
    limit: int = Query(default=20, ge=1, le=100),
    view: Literal["sessions", "records"] = Query(default="sessions"),
    source: str | None = Query(default=None, min_length=1),
    identity: IdentityContext = Depends(require_scope("search")),
) -> SessionListResponse:
    if view == "records":
        rows = list_recent_records(
            tenant_id=identity.tenant_id,
            principal_id=identity.principal_id,
            limit=limit,
            source=source,
        )
        return SessionListResponse(
            view=view,
            items=[SessionRecordListItem(**row) for row in rows],
        )

    rows = list_recent_sessions(
        tenant_id=identity.tenant_id,
        principal_id=identity.principal_id,
        limit=limit,
        source=source,
    )
    return SessionListResponse(
        view=view,
        items=[SessionListItem(**row) for row in rows],
    )


@app.get("/v1/sessions/{session_id}", response_model=SessionDetailResponse)
def get_session(
    session_id: str,
    source: str | None = Query(default=None, min_length=1),
    identity: IdentityContext = Depends(require_scope("search")),
) -> SessionDetailResponse:
    try:
        row = get_session_detail(
            tenant_id=identity.tenant_id,
            principal_id=identity.principal_id,
            session_id=session_id,
            source=source,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionDetailResponse(**row)
