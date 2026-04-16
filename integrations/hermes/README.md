# Capitok Memory Plugin for Hermes

Turn Hermes conversations into durable token assets.

This plugin connects Hermes to Capitok so every completed turn can be archived, recovered, searched, and reused later. The goal is not to replace Hermes memory. The goal is to keep the raw conversation your agent already paid for.

## Why Use It

With the Capitok plugin, Hermes can:

- Auto-save completed turns outside the active context window
- Keep conversation history portable across machines and runtime changes
- Search archived recall records with `capitok_recall`
- Explicitly save important context with `capitok_save`

If your Hermes session resets, your raw conversation archive still exists in Capitok.

## 1-Minute Setup

If you already cloned Capitok, the fastest path is:

```bash
hermes --version
bash scripts/install-hermes-plugin.sh
```

The installer copies `integrations/hermes` into your Hermes plugin directory and reads settings from shell env first, then from the repo's `.env` or `.env.dev`.

Capitok currently recommends Hermes `0.9.0` or newer. The installer checks your Hermes version and prints a warning if:

- Hermes is not installed or not in `PATH`
- the installed Hermes version looks older than `0.9.0`
- the installer cannot parse the Hermes version output

Installation still continues in all of these cases, but the plugin may not be fully compatible and may not work correctly on that Hermes version.

## Verify It Works

```bash
hermes plugins list
curl -i http://localhost:8000/health -H "X-API-Key: your-dev-api-key"
```

You should see:

- the `capitok` plugin enabled in Hermes
- a `200 OK` response from Capitok

You can then query archived recall records directly:

```bash
curl "http://localhost:8000/v1/search?query=test&top_k=5" \
  -H "X-API-Key: your-dev-api-key"
```

## What The Plugin Does

- Auto-saves each successful Hermes turn through the `post_llm_call` hook
- Registers `capitok_recall` for baseline recall
- Registers `capitok_save` for explicit save actions
- Works against any reachable Capitok endpoint over HTTP

## Configuration

### Recommended: use environment variables

```bash
export CAPITOK_API_URL=http://localhost:8000
export CAPITOK_API_KEY=your-dev-api-key
export CAPITOK_AUTO_SAVE=true
export CAPITOK_TIMEOUT=5.0
```

Then start Hermes:

```bash
hermes
```

### Alternative: configure in `~/.hermes/config.yaml`

```yaml
plugins:
  capitok:
    enabled: true
    api_url: http://localhost:8000
    api_key: your-dev-api-key
    auto_save: true
    timeout: 5.0
```

If you use the installer, it usually writes this block for you.

## Common Use Cases

### Automatic archive

Every successful turn is automatically saved after Hermes finishes responding.

### Search old context

```text
/capitok_recall query="topics about AI safety" top_k=5
```

Hermes can also call this tool when it needs prior context.

### Manually save important context

```text
/capitok_save note="Important: client wants quarterly reviews"
```

## Cross-Machine Setup

Run Capitok on one machine:

```bash
docker compose up
```

Then point Hermes on another machine to that endpoint:

```bash
export CAPITOK_API_URL=http://192.168.1.100:8000
export CAPITOK_API_KEY=your-dev-api-key
hermes
```

## Config Keys

| Key | Default | Description | Required |
|-----|---------|-------------|----------|
| `api_url` | `http://localhost:8000` | Capitok API endpoint | ✓ |
| `api_key` | - | Authentication key | ✓ |
| `auto_save` | `true` | Auto-save each successful turn | |
| `timeout` | `5.0` | HTTP timeout in seconds | |

## Troubleshooting

### Plugin not loading

```bash
hermes plugins list
echo $CAPITOK_API_KEY
curl http://localhost:8000/health
```

### Turns not being saved

```bash
hermes logs --since 10m
```

Check that `auto_save` is enabled and Capitok is reachable.

### Search returns no results

- Confirm data was ingested into Capitok
- Query `/v1/search` directly
- Check whether Hermes is searching under the expected user scope

In gateway or platform sessions, the plugin uses Hermes `user_id` from session context. In CLI sessions, it falls back to `cli:<session_id>`.

## Security

- All API calls use `X-API-Key`
- Store API keys in env vars or secure config, not in code
- Use HTTPS in production

Example:

```bash
export CAPITOK_API_URL=https://capitok.example.com
```

## Positioning

Capitok is best used here as a companion archive layer:

- Keep full Hermes turns as durable records
- Preserve raw conversation history before summarization or loss
- Support later replay, re-indexing, migration, and recovery
- Provide basic recall without trying to become the primary live memory framework

## License

Same as the Capitok project.
