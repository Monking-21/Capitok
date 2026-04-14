# Capitok Memory Plugin for Hermes

Auto-saves every Hermes conversation turn to Capitok so the raw conversation can be archived, recovered, and reused later.

## Quick Install

If you already cloned Capitok, install the plugin and sync Hermes config with one command:

```bash
bash scripts/install-hermes-plugin.sh
```

The installer copies `integrations/hermes` into your Hermes plugin directory and reads Capitok settings from the shell environment first, then from the repo's `.env` or `.env.dev`.
If you want to override values manually, export `CAPITOK_API_URL`, `CAPITOK_API_KEY`, `CAPITOK_AUTO_SAVE`, or `CAPITOK_TIMEOUT` before running the script.

## Positioning

Capitok is best used here as a companion archive layer:

- Preserve full Hermes turns outside the active context window
- Keep conversation history portable across machines and runtime changes
- Support later replay, re-indexing, or import into higher-level memory systems
- Provide basic recall without trying to become the primary memory framework

## Features

- **Auto-save**: Every turn is automatically saved to Capitok in background (non-blocking)
- **Baseline search**: Use `capitok_recall` tool to search past archived conversations
- **Manual save**: Use `capitok_save` tool to emphasize important context
- **Cross-machine**: Works with Capitok running on any accessible network address
- **Lightweight**: Uses standard library only, no external dependencies

## Installation

### 1. One-command install

```bash
bash scripts/install-hermes-plugin.sh
```

### 2. Configure Capitok endpoint manually

**Option A: Environment variables (recommended for servers)**

```bash
export CAPITOK_API_URL=http://localhost:8000        # or http://192.168.x.x:8000
export CAPITOK_API_KEY=dev-ingest-search-key        # from your Capitok .env
export CAPITOK_AUTO_SAVE=true
```

Then start Hermes:
```bash
hermes
```

**Option B: config.yaml (recommended for persistent config)**

Edit `~/.hermes/config.yaml`:
```yaml
plugins:
  capitok:
    enabled: true
    api_url: http://localhost:8000
    api_key: dev-ingest-search-key
    auto_save: true
    timeout: 5.0
```

**Option C: Interactive setup**

```bash
hermes plugins  # Navigate to Capitok plugin and configure
```

If you use the installer, it will write the Capitok block for you, so you usually do not need to edit `config.yaml` manually.

## Configuration

| Key | Default | Description | Required |
|-----|---------|-------------|----------|
| `api_url` | `http://localhost:8000` | Capitok API endpoint | ✓ |
| `api_key` | - | Authentication key (from Capitok `.env`) | ✓ |
| `auto_save` | `true` | Auto-save each turn | |
| `timeout` | `5.0` | HTTP request timeout in seconds | |

## Usage

### Automatic saving (always on if configured)

Every turn is automatically saved:
```
User: "What are my project deadlines?"
Hermes: "Based on your memories, you have..."
[Capitok plugin saves this turn in background]
```

### Search memories with `capitok_recall`

In conversation:
```
/capitok_recall query="topics about AI safety" top_k=5
```

Or let Hermes use it autonomously:
```
User: "Remind me what we discussed about security last month"
Hermes: [uses capitok_recall to search] "We discussed..."
```

### Manual save with `capitok_save`

```
/capitok_save note="Important: client wants quarterly reviews"
```

Or Hermes can use it:
```
User: "Remember this: we need to increase the budget by 20%"
Hermes: [uses capitok_save to emphasize] "Saved that important update"
```

## Cross-machine setup

**Capitok on server A (192.168.1.100):**
```bash
# In /home/user/Capitok
docker compose up  # Runs on port 8000
```

**Hermes on server B:**
```bash
export CAPITOK_API_URL=http://192.168.1.100:8000
export CAPITOK_API_KEY=dev-ingest-search-key
hermes
```

## Verify working

### Check plugin is loaded

```bash
hermes doctor
# Look for:
# Plugins: capitok ... OK
```

### Manual test of connection

```bash
# From Hermes server
curl -i http://localhost:8000/health -H "X-API-Key: dev-ingest-search-key"
# Should return: 200 OK
```

### Check saved memories

```bash
# Query Capitok directly
curl "http://localhost:8000/v1/search?query=test&top_k=5" \
  -H "X-API-Key: dev-ingest-search-key"
```

## Troubleshooting

### Plugin not loading

1. Check if Capitok API is reachable:
   ```bash
   curl http://localhost:8000/health
   ```

2. Check if `CAPITOK_API_KEY` is set:
   ```bash
   echo $CAPITOK_API_KEY
   ```

3. Check Hermes logs:
   ```bash
   hermes doctor
   ```

### Turns not being saved

1. Check if `auto_save` is enabled:
   ```yaml
   # In ~/.hermes/config.yaml
   plugins:
     capitok:
       auto_save: true  # Should be true
   ```

2. Check Hermes logs for errors:
   ```bash
   # Hermes logs usually go to stdout, check for "Capitok" messages
   ```

### Search returns no results

1. Verify data was ingested:
   - Check Capitok logs: `docker logs capitok-api-dev`
   - Query Capitok's `/v1/search` endpoint manually

2. Check if search is using correct `user_id`:
   - The plugin uses Hermes `user_id` from session context
   - Searches are scoped by user (not global)

## Architecture

```
Hermes Agent
    ↓
turns → Capitok Plugin (on_turn_end hook)
    ↓
Capitok /v1/ingest
    ↓
PostgreSQL (raw_chat_logs, refined_memories)
    ↓
Hermes tools: capitok_recall, capitok_save
    ↓
Agent retrieves context when needed
```

## Performance

- **Auto-save**: ~100ms background save (non-blocking)
- **Search**: environment-dependent baseline recall over derived records
- **Network**: Works over any HTTP connection

Capitok is designed for long-term durability and recovery of conversation assets, not for taking over the primary memory framework role in real-time reasoning.

## Security

- All API calls use `X-API-Key` header authentication
- API keys should be stored in env vars or secure config, never in code
- In production, use TLS/HTTPS for Capitok endpoint:
  ```bash
  export CAPITOK_API_URL=https://capitok.example.com
  ```

## License

Same as Capitok project (see Capitok's LICENSE file).
