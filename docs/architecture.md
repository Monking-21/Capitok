# Architecture Design

This document describes the technical design goals, architecture, storage model, and operational strategy for Capitok.

Capitok is positioned as a raw conversation archive and recovery substrate for agent systems.
It complements upstream memory frameworks by preserving source conversations so they can be replayed, re-indexed, or reconstructed later.

## Design Principles (Avoid Over-Engineering)

Capitok uses a boundary-first and implementation-later strategy:

- Define extensibility boundaries early to avoid expensive rewrites
- Implement only MVP-critical capabilities in the first release
- Keep production-grade capabilities as pluggable reserved designs

## Phased Scope

### MVP (must-have)

- Basic authentication (API key or JWT)
- Raw ingest and durable archive boundary
- Baseline retrieval over derived records
- Backup and restore scripts

### Reserved (optional for first release)

- Full multi-tenant RBAC
- Durable queue with retry and dead-letter handling
- Full audit trail and compliance deletion workflows
- Custom operations dashboard

## Design Goals

- Preserve raw agent conversations as durable assets
- Keep migration and recovery cost low through an independent archive layer
- Make replay, re-indexing, and downstream memory reconstruction possible
- Provide baseline retrieval without positioning itself as the primary memory framework

## Logical Architecture

```text
[ Agent Layer ]         OpenClaw (Plugin) / Hermes (Provider)
                               |
                               v
[ Middleware Layer ]    FastAPI Gateway (Archive / Recovery MaaS)
                     /        |        \
      (sync raw)  /   (async derive)   \ (sync search)
                   /         |          \
[ Storage Layer ]  Raw Postgres   Optional Upstream Memory Logic   Derived Postgres
                  (JSONB)             (Mem0 etc.)                  (FTS / future vector)
```

## Storage Model (PostgreSQL 16+)

Use one PostgreSQL cluster with logical separation for hot and cold data.

### Table A: raw_chat_logs

Purpose:
- Persist every interaction as raw JSON
- Act as the source-of-truth archive for recovery and replay

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
- Store derived searchable records built from the raw archive

Core design:
- Full-text column: tsvector for baseline keyword recall
- Embedding column is reserved for future downstream integrations
- Derived records can be rebuilt from raw archive data when indexing strategy changes
- Retrieval quality is secondary to raw data durability in the MVP

Suggested additional fields:
- tenant_id (text)
- principal_id (text)
- embedding_version (text)
- updated_at (timestamptz)

Performance note:
- Performance targets should be treated as environment-specific benchmarks, not product guarantees.

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
2. Point Hermes archive or memory-facing endpoint to the FastAPI gateway.
3. Enable trace-level logs only during troubleshooting.

## FastAPI Archive + Optional Memory Flow

```py
from fastapi import BackgroundTasks, FastAPI

app = FastAPI()

@app.post("/v1/ingest")
async def ingest_memory(data: dict, bg: BackgroundTasks):
    save_to_raw_db(data)

    text = f"{data.get('input', '')}\n{data.get('output', '')}"
    bg.add_task(save_derived_record, text, user_id=data["user_id"])
    # Future: replay raw records into Mem0 or another memory framework when needed.

    return {"status": "queued"}

@app.get("/v1/search")
async def search_memory(query: str, user_id: str):
    return search_derived_records(query, user_id=user_id)
```

Reliability note:
- The raw archive path is the critical durability boundary.
- Replace in-process background tasks with a durable queue when derived indexing becomes operationally important.

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
- Prioritize the raw archive for recovery guarantees.
- Dump both raw and derived tables when derived retrieval state matters operationally.

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
- Basic alerts for error rate, archive write failures, queue lag, and retrieval latency

### Enhanced (visual operations)

- Use Grafana or similar tooling for dashboards
- Build custom frontend console only when product workflows require it

## Risk Model

- Upstream memory-framework replacement risk: raw data remains in PostgreSQL
- Model migration risk: derived records and embeddings can be regenerated from raw logs
- Agent crash risk: archive service remains independent
