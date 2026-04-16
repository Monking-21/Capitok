#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$repo_root"

uv run --no-project --isolated python - <<'PY'
from integrations.codex.payloads import normalize_event

session_start = {
    "event": "SessionStart",
    "session_id": "codex-session-1",
    "cwd": "/tmp/project",
    "timestamp": 123.0,
}

user_prompt = {
    "event": "UserPromptSubmit",
    "session_id": "codex-session-1",
    "prompt": "Summarize this file",
}

pre_tool = {
    "event": "PreToolUse",
    "session_id": "codex-session-1",
    "tool_name": "Bash",
    "tool_input": {"command": "ls -la"},
}

post_tool = {
    "event": "PostToolUse",
    "session_id": "codex-session-1",
    "tool_name": "Bash",
    "tool_input": {"command": "ls -la"},
    "tool_output": {"stdout": "README.md", "exit_code": 0},
}

stop_event = {
    "event": "Stop",
    "session_id": "codex-session-1",
    "reason": "completed",
}

real_user_prompt = {
    "hook_event_name": "UserPromptSubmit",
    "session_id": "codex-session-2",
    "prompt": "real hook prompt",
}

real_stop_event = {
    "hook_event_name": "Stop",
    "session_id": "codex-session-2",
    "last_assistant_message": "assistant final text",
}

assert normalize_event(session_start)["source"] == "codex"
assert normalize_event(user_prompt)["input"] == "Summarize this file"
assert "ls -la" in normalize_event(pre_tool)["input"]
assert "README.md" in normalize_event(post_tool)["output"]
assert normalize_event(stop_event)["metadata"]["event_type"] == "Stop"
assert normalize_event(real_user_prompt)["input"] == "real hook prompt"
assert normalize_event(real_stop_event)["output"] == "assistant final text"
PY
