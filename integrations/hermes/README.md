# Capitok Memory Plugin for Hermes

Auto-saves every Hermes conversation turn to Capitok memory gateway for persistent storage and retrieval.

## Features

- **Auto-save**: Every turn is automatically saved to Capitok in background (non-blocking)
- **Semantic search**: Use `capitok_recall` tool to search past conversations
- **Manual save**: Use `capitok_save` tool to emphasize important context
- **Cross-machine**: Works with Capitok running on any accessible network address
- **Lightweight**: Uses standard library only, no external dependencies

## Installation

### 1. Copy plugin to Hermes

```bash
# Clone or copy Capitok repo first if not already done
git clone https://github.com/yourusername/Capitok.git

# Copy the plugin to Hermes plugins directory
cp -r Capitok/integrations/hermes ~/.hermes/plugins/capitok
# Or if you're developing locally:
cp -r Capitok/integrations/hermes /path/to/hermes-agent/plugins/capitok
```

### 2. Configure Capitok endpoint

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
- **Search**: ~50ms (with 100k memories in database)
- **Network**: Works over any HTTP connection

Capitok is designed for long-term memory durability, not real-time processing.

## Security

- All API calls use `X-API-Key` header authentication
- API keys should be stored in env vars or secure config, never in code
- In production, use TLS/HTTPS for Capitok endpoint:
  ```bash
  export CAPITOK_API_URL=https://capitok.example.com
  ```

## License

Same as Capitok project (see Capitok's LICENSE file).
