# Implementation Status and Plan

This document tracks what has already been implemented and what comes next.

## 1. Completed Work

### 1.1 API and Service Skeleton

- FastAPI app bootstrap and routes are implemented.
- Endpoints available:
  - `GET /health`
  - `POST /v1/ingest`
  - `GET /v1/search`

Files:
- [src/capitok/main.py](../src/capitok/main.py)
- [src/capitok/schemas.py](../src/capitok/schemas.py)

### 1.2 Security Boundary (MVP)

- API key authentication is implemented.
- Identity is derived from server-side API key mapping.
- Tenant and principal scoped checks are enforced through required scopes.

Files:
- [src/capitok/security.py](../src/capitok/security.py)
- [src/capitok/config.py](../src/capitok/config.py)

### 1.3 Storage and Data Model

- PostgreSQL schema created for:
  - `raw_chat_logs`
  - `refined_memories`
- FTS index and vector extension are prepared.
- SQL schema now includes maintainability comments for isolation, embedding versioning, and search behavior.
- Alembic migration workflow is now the primary way to evolve database structure.
- Schema snapshot automation script added to export `sql/schema.sql` from the live database.

Files:
- [sql/schema.sql](../sql/schema.sql)
- [src/capitok/db.py](../src/capitok/db.py)

### 1.4 Queue Abstraction (Reserved Design + MVP Backend)

- Queue interface is defined.
- In-process async adapter is implemented for MVP.

Files:
- [src/capitok/queue/interface.py](../src/capitok/queue/interface.py)
- [src/capitok/queue/inprocess.py](../src/capitok/queue/inprocess.py)

### 1.5 Operability Baseline

- Docker Compose split into explicit profiles:
  - `docker-compose.yml` default production-oriented deployment
  - `docker-compose.dev.yml` dedicated development/testing profile
- Environment template added.
- Development environment file added (`.env.dev`).
- Backup and restore scripts added.
- Migration helper script added.
- DB readiness helper script added for compose startup.
- Schema dump helper script added.
- Unified API startup script added (`scripts/start-api.sh`).
- OpenAPI contract file added.
- uv is now the default package manager and command runner.
- Documentation now includes a dedicated implementation status file and repository structure updates for src layout.

Files:
- [docker-compose.yml](../docker-compose.yml)
- [docker-compose.dev.yml](../docker-compose.dev.yml)
- [Dockerfile](../Dockerfile)
- [.env.example](../.env.example)
- [.env.dev](../.env.dev)
- [scripts/backup.sh](../scripts/backup.sh)
- [scripts/restore.sh](../scripts/restore.sh)
- [scripts/start-api.sh](../scripts/start-api.sh)
- [openapi.yaml](../openapi.yaml)

## 2. In Progress

- Align implementation details with architecture docs for hybrid retrieval behavior.
- Add basic tests for ingest and search paths.
- Review whether the initial refined-memory write path should stay simple text-first until Mem0 embedding integration is finalized.

## 3. Next-Step Development Plan

### Phase A (Now -> v0.1.1)

1. Add test suite
- unit tests for auth and scope checks
- integration tests for ingest/search happy path

2. Improve error handling
- normalized error payloads
- better DB and queue failure visibility

3. Add metrics endpoint
- ingest success/failure counters
- search latency histogram

4. Review SQL migration safety
- verify schema creation against target PostgreSQL + pgvector versions
- decide whether ANN index creation should stay in the initial migration or move to a follow-up migration

5. Add migration workflow docs
- document revision naming convention and upgrade/downgrade usage
- clarify that `schema.sql` is a reference snapshot, not the main change path

6. Add CI schema drift check
- run migrations on ephemeral DB
- run schema dump and assert no diff against tracked `sql/schema.sql`

### Phase B (v0.2)

1. Durable queue adapter
- Redis Streams first option
- retry and dead-letter support

2. Hybrid retrieval upgrade
- combine FTS and vector scores explicitly
- add ranking config switches

3. Mem0 adapter refinement
- plug in embedding generation path
- keep `embedding_version` strategy consistent

### Phase C (v0.3+)

1. Multi-tenant hardening
- tighter policy model beyond API key scopes
- audit-oriented event trail

2. Operator observability
- Prometheus + Grafana baseline dashboards
- optional custom frontend only if workflow requires it

## 4. Decision: Root Folder Name vs `capitok/` Package Folder

Question: the repository is already named Capitok, so is an additional `capitok/` directory reasonable?

Answer: yes, this is a standard Python layout.

Reason:
- Repository folder is project/workspace identity.
- Inner `capitok/` is the importable Python package namespace.
- This avoids ambiguous imports and keeps code modular.

Current choice:
- Keep repository root as `Capitok`.
- Keep application package as `capitok`.

Alternative (optional later):
- Move to `src/capitok/` layout for stricter packaging isolation.
