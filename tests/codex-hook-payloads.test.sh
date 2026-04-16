#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$repo_root"

uv run --no-project --isolated python - <<'PY'
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

from integrations.codex.payloads import (
    build_transcript_snapshot_payload,
    extract_transcript_path,
    normalize_event,
)

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

transcript_event = {
    "hook_event_name": "Stop",
    "session_id": "codex-session-3",
    "transcript_path": "/tmp/codex-session-3.jsonl",
}

assert normalize_event(session_start)["source"] == "codex"
assert normalize_event(user_prompt)["input"] == "Summarize this file"
assert "ls -la" in normalize_event(pre_tool)["input"]
assert "README.md" in normalize_event(post_tool)["output"]
assert normalize_event(stop_event)["metadata"]["event_type"] == "Stop"
assert normalize_event(real_user_prompt)["input"] == "real hook prompt"
assert normalize_event(real_stop_event)["output"] == "assistant final text"

assert extract_transcript_path(transcript_event) == "/tmp/codex-session-3.jsonl"

with TemporaryDirectory() as tmpdir:
    transcript_path = Path(tmpdir) / "session.jsonl"
    raw_transcript_jsonl = "\n".join(
        [
            '{"type":"message","text":"hello"}',
            '{"type":"message","text":"world"}',
        ]
    ) + "\n"
    transcript_path.write_text(raw_transcript_jsonl, encoding="utf-8")

    payload = build_transcript_snapshot_payload("codex-session-3", "user-3", transcript_path)
    expected_bytes = raw_transcript_jsonl.encode("utf-8")

    assert payload["session_id"] == "codex-session-3"
    assert payload["user_id"] == "user-3"
    assert payload["source"] == "codex"
    assert payload["input"] == ""
    assert payload["output"] == "transcript snapshot archived"
    assert payload["metadata"]["event_type"] == "TranscriptSnapshot"
    assert payload["metadata"]["origin_event_type"] == "Stop"
    assert payload["metadata"]["transcript_path"] == str(transcript_path)
    assert payload["metadata"]["transcript_sha256"] == hashlib.sha256(expected_bytes).hexdigest()
    assert payload["metadata"]["transcript_bytes"] == len(expected_bytes)
    assert payload["metadata"]["transcript_line_count"] == 2
    assert payload["metadata"]["raw_transcript_jsonl"] == raw_transcript_jsonl
PY
