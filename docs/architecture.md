# Architecture Design

This document describes the technical design goals, architecture, storage model, and operational strategy for Capitok.

## Design Principles (Avoid Over-Engineering)

Capitok uses a boundary-first and implementation-later strategy:

- Define extensibility boundaries early to avoid expensive rewrites
- Implement only MVP-critical capabilities in the first release
- Keep production-grade capabilities as pluggable reserved designs

## Phased Scope

### MVP (must-have)

- Basic authentication (API key or JWT)
- Raw ingest and baseline retrieval
- Minimal hybrid search (vector + full-text)
- Backup and restore scripts

### Reserved (optional for first release)

- Full multi-tenant RBAC
- Durable queue with retry and dead-letter handling
- Full audit trail and compliance deletion workflows
- Custom operations dashboard

## Design Goals

- Maximum data safety with master-grade backups
- Industrial retrieval performance with hybrid search
- Low migration and recovery cost via containerized deployment

## Logical Architecture

```text
[ Agent Layer ]         OpenClaw (Plugin) / Hermes (Provider)
                               |
                               v
[ Middleware Layer ]    FastAPI Gateway (Memory MaaS)
                     /        |        \
       (async raw) /   (async refine)  \ (sync search)
                   /         |          \
[ Storage Layer ]  Raw Postgres   Mem0 Logic   Refined Postgres
                  (JSONB)       (processor)    (pgvector + tsvector)
```

## Storage Model (PostgreSQL 16+)

Use one PostgreSQL cluster with logical separation for hot and cold data.

### Table A: raw_chat_logs

Purpose:
- Persist every interaction as raw JSON

Core fields:
- id (uuid)
- tenant_id (text)
- principal_id (text)
- session_id (text)
- user_id (text)
- agent_id (text)
- source (text)
- content (jsonb)
- created_at (timestamptz)

### Table B: refined_memories

Purpose:
- Store distilled atomic facts for retrieval

Core design:
- Embedding column: vector(1536) or model-aligned dimensions
- Full-text column: tsvector for exact keyword recall
- Hybrid retrieval: vector similarity + FTS ranking
- ANN index: HNSW for scalable latency

Suggested additional fields:
- tenant_id (text)
- principal_id (text)
- embedding_version (text)
- updated_at (timestamptz)

Performance note:
- Treat p95 < 20ms at 100k memories as a benchmark target, not a hard guarantee.

## Integration Plan

### Identity and Tenant Boundary (must enforce)

To prevent cross-tenant access, identity must not be client-asserted in request body:

1. Client sends only token (API key or JWT).
2. Gateway resolves tenant_id, principal_id, and scopes from token.
3. Service enforces tenant_id and principal_id in writes and queries.
4. user_id in payload is business metadata, not an authorization source.

Recommended isolation levels:

- L1: tenant isolation (required)
- L2: principal/user isolation (product-driven)
- L3: agent channel identity (audit-focused)

### OpenClaw Hook Example

```ts
onResponseGenerated: async (context) => {
  const payload = {
    user_id: "weiling",
    input: context.message.content,
    output: context.response.content,
    metadata: { agent: "OpenClaw", model: context.model },
  };

  fetch("http://localhost:8000/v1/ingest", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-API-Key": "${MEMORY_API_KEY}" },
    body: JSON.stringify(payload),
  }).catch(() => {
    // Production clients should add retry or local queue fallback.
  });
};
```

### Hermes Provider Setup

1. Choose PostgreSQL as storage backend.
2. Point Hermes memory endpoint to FastAPI gateway.
3. Enable trace-level logs only during troubleshooting.

## FastAPI + Mem0 Core Flow

```py
from fastapi import BackgroundTasks, FastAPI
from mem0 import Memory

app = FastAPI()

m = Memory.from_config({
    "vector_store": {
        "provider": "pgvector",
        "config": {
            "connection_string": "postgresql://postgres:pass@localhost:5432/memory_db"
        },
    }
})

@app.post("/v1/ingest")
async def ingest_memory(data: dict, bg: BackgroundTasks):
    bg.add_task(save_to_raw_db, data)

    text = f"{data.get('input', '')}\n{data.get('output', '')}"
    bg.add_task(m.add, text, user_id=data["user_id"])

    return {"status": "queued"}

@app.get("/v1/search")
async def search_memory(query: str, user_id: str):
    return m.search(query, user_id=user_id)
```

Reliability note:
- Replace in-process background tasks with a durable queue in production.

### Queue Abstraction (reserved interface)

To keep MVP simple while preserving future scalability, define a queue interface now:

- enqueue_ingest_task(payload)
- enqueue_refine_task(payload)
- handle_retry(task_id)
- move_to_dead_letter(task_id)

Later implementations can use Redis Streams, RabbitMQ, or Postgres-based queues.

## Deployment and Security

1. Containerization:
- Run PostgreSQL (with pgvector) and FastAPI gateway in docker compose.
- Mount DB data to encrypted disk or NAS.

2. Backups:
- Schedule nightly dumps for both raw and refined tables.

```bash
pg_dump -t raw_chat_logs -t refined_memories memory_db > memory_backup.sql
```

3. Access control:
- Enforce API key or JWT.
- Add TLS, key rotation, and request audit logs.

## Observability and Dashboard

### MVP (no custom frontend required)

- Expose metrics endpoint (for example Prometheus)
- Structured logs with trace_id and tenant_id
- Basic alerts for error rate, queue lag, and retrieval latency

### Enhanced (visual operations)

- Use Grafana or similar tooling for dashboards
- Build custom frontend console only when product workflows require it

## Risk Model

- Mem0 replacement risk: data remains in PostgreSQL
- Model migration risk: embeddings can be regenerated from raw logs
- Agent crash risk: memory service remains independent