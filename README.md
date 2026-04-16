# Capitok

Capitok helps you capitalize your token.

`Capitok` comes from `capitalize your token`: turn the context and token cost your agents have already spent into durable, reusable assets.

Capitok is an open-source raw conversation archive and recovery layer for AI agents. It stores full interaction records before they disappear from the context window, so they can later be replayed, re-indexed, migrated, and reused across devices, runtimes, and frameworks.

## What Capitok Does

- Archives raw agent conversations before they are lost
- Turns spent token history into portable conversation assets
- Provides a recovery layer for replay, re-indexing, and future memory rebuilding
- Complements higher-level memory frameworks instead of replacing them

## Why It Matters

Most agent systems already pay to generate valuable conversation history, but that history is often trapped inside a single runtime, context window, or framework.

Capitok treats those consumed tokens as assets:

- Keep the raw conversation, not just a summary
- Survive context resets, machine changes, and framework migrations
- Preserve a source-of-truth archive for future memory pipelines
- Build retrieval on top of the archive instead of making retrieval the archive

## Quick Start

### 1. Start Capitok locally

```bash
git clone https://github.com/Monking-21/Capitok.git
cd Capitok
cp .env.example .env
docker compose up --build
```

### 2. Verify the API

```bash
curl http://localhost:8000/health
```

### 3. Archive one interaction

```bash
curl -X POST "http://localhost:8000/v1/ingest" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: replace-with-prod-key" \
  -d '{
    "session_id": "s-001",
    "user_id": "u-001",
    "source": "agent",
    "input": "I like Tushare API",
    "output": "Noted, preference stored.",
    "metadata": {"agent": "OpenClaw"}
  }'
```

### 4. Search archived recall records

```bash
curl "http://localhost:8000/v1/search?query=Tushare&top_k=5" \
  -H "X-API-Key: replace-with-prod-key"
```

For local development, you can also use the committed dev profile:

```bash
docker compose -f docker-compose.dev.yml up --build
```

That profile uses `.env.dev` and includes the local testing key `dev-ingest-search-key`.

## CLI

Capitok also provides a thin session-first CLI for source-checkout workflows:

```bash
uv run capitok health
uv run capitok sessions list
uv run capitok sessions show <session_id> --source codex
uv run capitok search "quarterly review"
uv run capitok codex enable
uv run capitok hermes enable
```

The CLI reuses the same repo-local config resolution as the Codex integration:

- explicit `CAPITOK_API_URL` / `CAPITOK_API_KEY`
- otherwise `.env`
- otherwise `.env.dev`

## Integration

### Hermes integration

If you already use Hermes, the fastest path is:

```bash
hermes --version
bash scripts/install-hermes-plugin.sh
```

Then verify:

```bash
hermes plugins list
curl -i http://localhost:8000/health -H "X-API-Key: dev-ingest-search-key"
```

The Hermes plugin currently:

- Auto-saves completed turns through the `post_llm_call` hook
- Exposes `capitok_recall` for baseline recall
- Exposes `capitok_save` for explicit save actions

The installer copies `integrations/hermes` into your Hermes plugin directory and reads settings from shell env first, then from `.env` or `.env.dev`.
Capitok currently recommends Hermes `0.9.0` or newer. The installer warns if Hermes is missing, older, or its version cannot be detected, but it does not block installation.

You can override these before installation:

- `CAPITOK_API_URL`
- `CAPITOK_API_KEY`
- `CAPITOK_AUTO_SAVE`
- `CAPITOK_TIMEOUT`

Full guide: [integrations/hermes/README.md](integrations/hermes/README.md)

### Codex integration

If you use Codex hooks, Capitok can archive supported hook events for later recovery without replacing Codex's own memory behavior.
Installing the Codex integration replaces any existing handlers for Capitok's supported Codex events: `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, and `Stop`.
Install with `bash scripts/install-codex-hook.sh`.

Full guide: [integrations/codex/README.md](integrations/codex/README.md)

### Direct API integration

If you are building your own agent runtime, point your application to Capitok's HTTP API:

- `POST /v1/ingest` to archive raw interactions
- `GET /v1/search` to retrieve derived recall records
- `GET /v1/sessions` to list recent archived sessions or raw records
- `GET /v1/sessions/{session_id}` to inspect one archived session timeline
- `GET /health` for service checks

Authentication uses the `X-API-Key` header. Tenant and principal identity are derived server-side from the API key mapping.

## Who It Is For

- Agent builders who want durable conversation archives
- Infra teams who need a framework-independent recovery layer
- Teams that want to keep raw conversation assets before building richer memory systems

## Project Positioning

Capitok is not trying to be the primary real-time semantic memory framework.

It is designed as:

- A raw-first archive layer
- A recovery substrate for future replay and reconstruction
- A middleware boundary between agent runtimes and stored conversation assets
- A foundation on top of which richer memory workflows can be built

## Current MVP

Current MVP supports:

1. API key auth with tenant and principal mapping
2. Raw chat log persistence
3. Async in-process derived-text write path
4. Tenant and principal scoped baseline search
5. Alembic-based database migrations as the primary schema workflow
6. Automated schema snapshot export from database
7. `uv` as the default package manager and command runner
8. Dual compose model: default production plus explicit dev/test profile

Current MVP does not aim to be a full semantic memory framework.
The searchable `refined_memories` table is a derived layer intended to support recall and future reconstruction workflows on top of the raw archive.

## Repository Structure

```text
.
├── README.md
├── README.zh-CN.md
├── .env.dev
├── pyproject.toml
├── alembic.ini
├── docker-compose.yml
├── docker-compose.dev.yml
├── Dockerfile
├── migrations/
│   ├── env.py
│   └── versions/
├── sql/
│   └── schema.sql
├── scripts/
│   ├── backup.sh
│   ├── dump-schema.sh
│   ├── migrate.sh
│   ├── start-api.sh
│   ├── wait-for-db.sh
│   └── restore.sh
├── src/
│   └── capitok/
│       ├── main.py
│       ├── config.py
│       ├── security.py
│       ├── db.py
│       ├── schemas.py
│       └── queue/
│           ├── interface.py
│           └── inprocess.py
└── docs/
    ├── architecture.md
    ├── architecture.zh-CN.md
    ├── implementation-status.md
    └── implementation-status.zh-CN.md
```

## Documentation

- Architecture (English): [docs/architecture.md](docs/architecture.md)
- Architecture (Chinese): [docs/architecture.zh-CN.md](docs/architecture.zh-CN.md)
- Implementation Status and Plan (English): [docs/implementation-status.md](docs/implementation-status.md)
- 实施进展与下一步计划（中文）: [docs/implementation-status.zh-CN.md](docs/implementation-status.zh-CN.md)
- Hermes integration guide: [integrations/hermes/README.md](integrations/hermes/README.md)
- Codex integration guide: [integrations/codex/README.md](integrations/codex/README.md)
- Chinese README: [README.zh-CN.md](README.zh-CN.md)

## Schema Workflow

1. Apply migrations.
2. Run `./scripts/dump-schema.sh` to refresh `sql/schema.sql`.

## Roadmap

1. MVP architecture freeze
2. API contract and schema definitions
3. Durable queue adapter such as Redis Streams or RabbitMQ
4. Observability and reliability hardening
5. Community feedback and iteration

## Contributing

Contributions are welcome after the initial implementation scaffold is published.

Planned contribution scope:

1. API design reviews
2. Storage schema proposals
3. Benchmark scripts
4. Reliability and security improvements

## License

License is not finalized yet.

Planned options:

1. MIT
2. Apache-2.0

## Language

English is the default language for global collaboration. Chinese docs are provided as reference.
