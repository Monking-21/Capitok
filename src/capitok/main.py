from fastapi import Depends, FastAPI, Query

from capitok.config import get_settings
from capitok.db import insert_raw_chat_log, search_refined_memories
from capitok.queue.inprocess import InProcessQueueAdapter
from capitok.queue.interface import RefineTask
from capitok.schemas import IngestRequest, IngestResponse, SearchResponse, SearchResult
from capitok.security import IdentityContext, require_scope

settings = get_settings()
app = FastAPI(title=settings.app_name)
queue_adapter = InProcessQueueAdapter()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "env": settings.app_env}


@app.post("/v1/ingest", response_model=IngestResponse)
async def ingest_memory(
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

    return IngestResponse(status="queued", message="Ingest accepted")


@app.get("/v1/search", response_model=SearchResponse)
def search_memory(
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
