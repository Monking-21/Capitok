# Capitok

Capitok is an open-source memory architecture for AI agents focused on recoverability, retrieval quality, and migration safety.

## Project Status

- Stage: MVP scaffold in progress
- Code implementation: Initial FastAPI gateway and DB schema available
- Main target users: AI agent builders and infrastructure engineers

## Highlights

- Raw-first data strategy for long-term recoverability
- Hybrid retrieval design (vector + full-text)
- Middleware decoupling between agent runtime and memory storage
- Container-first operations model for portability

## Documentation

- Architecture (English): [docs/architecture.md](docs/architecture.md)
- Architecture (Chinese): [docs/architecture.zh-CN.md](docs/architecture.zh-CN.md)
- Implementation Status and Plan (English): [docs/implementation-status.md](docs/implementation-status.md)
- 实施进展与下一步计划（中文）: [docs/implementation-status.zh-CN.md](docs/implementation-status.zh-CN.md)
- Hermes integration guide: [integrations/hermes/README.md](integrations/hermes/README.md)
- Chinese README: [README.zh-CN.md](README.zh-CN.md)

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

## Quick Start

### Production (default)

1. Install uv:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Create environment file:

```bash
cp .env.example .env
```

3. Start production-oriented default stack:

```bash
docker compose up --build
```

### Development and Testing

1. Use the dedicated dev/test compose file:

```bash
docker compose -f docker-compose.dev.yml up --build
```

This profile uses the committed `.env.dev` file by default.

### Basic Verification

1. Health check:

```bash
curl http://localhost:8000/health
```

2. Ingest example:

```bash
curl -X POST "http://localhost:8000/v1/ingest" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: dev-ingest-search-key" \
    -d '{
        "session_id": "s-001",
        "user_id": "u-001",
        "source": "openclaw",
        "input": "I like Tushare API",
        "output": "Noted, preference stored.",
        "metadata": {"agent": "OpenClaw"}
    }'
```

3. Search example:

```bash
curl "http://localhost:8000/v1/search?query=Tushare&top_k=5" \
    -H "X-API-Key: dev-ingest-search-key"
```

### Hermes Integration

Install and configure the Hermes plugin in one command:

```bash
bash scripts/install-hermes-plugin.sh
```

Then verify it:

```bash
hermes doctor
curl -i http://localhost:8000/health -H "X-API-Key: dev-ingest-search-key"
```

The installer copies `integrations/hermes` into your Hermes plugin directory and reads Capitok settings from the shell environment first, then from the repo's `.env` or `.env.dev`.
You can still override values by exporting `CAPITOK_API_URL`, `CAPITOK_API_KEY`, `CAPITOK_AUTO_SAVE`, or `CAPITOK_TIMEOUT` before running it.

Current MVP supports:

1. API key auth with tenant and principal mapping
2. Raw chat log persistence
3. Async in-process refinement queue
4. Tenant and principal scoped search
5. Alembic-based database migrations as the primary schema workflow
6. Automated schema snapshot export from database
7. uv as the default package manager and command runner
8. Dual compose model: default production + explicit dev/test profile

For the full Hermes plugin guide, see [integrations/hermes/README.md](integrations/hermes/README.md).

Schema snapshot workflow:

1. Apply migrations.
2. Run `./scripts/dump-schema.sh` to refresh `sql/schema.sql`.

## Roadmap

1. MVP architecture freeze
2. API contract and schema definitions
3. Durable queue adapter (Redis Streams or RabbitMQ)
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