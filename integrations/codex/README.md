# Capitok Codex Integration

This integration archives Codex hook events into Capitok so you can keep a raw conversation record outside the active session window. It is a lightweight archive companion, not a proxy, and not a replacement for Codex memory behavior.

## What It Does

- Copies supported Codex hook events into Capitok through the ingest API
- Preserves raw event payloads alongside a normalized archive record
- Helps keep session history available for later replay, re-indexing, and recovery

## V1 Event Coverage

The current V1 integration covers these Codex hook events:

- `SessionStart`
- `UserPromptSubmit`
- `PreToolUse`
- `PostToolUse`
- `Stop`

## V1 Limits

- Coverage depends on Codex hooks being available and enabled in the local Codex environment
- Tool coverage is incomplete and currently reflects the hook payloads Codex provides
- Non-`Bash` tools may expose less detail than shell commands
- This is not full token capture; it archives hook-visible event data, not every token generated in Codex internals

## Install

```bash
bash scripts/install-codex-hook.sh
```

Run this from the repository root. The script switches into the repo root, uses `uv` to run the installer, writes the Codex hook configuration under `~/.codex`, and points the hooks at the local `integrations/codex/hook_runtime.py` entrypoint.

If you need the lower-level entrypoint directly, it is still:

```bash
uv run python integrations/codex/install.py
```

The hook runtime resolves Capitok settings in this order:

- explicit `CAPITOK_API_URL` and `CAPITOK_API_KEY` from the current shell
- otherwise the repository `.env`
- otherwise the repository `.env.dev`

If no explicit `CAPITOK_API_KEY` is set, the runtime can reuse `AUTH_API_KEYS_JSON` only when that map contains exactly one API key.

Installing also takes over the supported Codex event slots listed above. If `~/.codex/hooks.json` already defines handlers for `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, or `Stop`, the installer replaces those commands with the Capitok hook command and leaves unrelated hook entries untouched.

## Positioning

Capitok uses the Codex integration as a lightweight archive companion:

- It stores hook-visible interaction data for later recovery
- It does not sit inline as a proxy between Codex and its tools
- It does not replace Codex's own memory or session behavior
- It is meant to preserve raw records first, then let higher-level workflows build on top
