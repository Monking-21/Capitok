from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any


SUPPORTED_EVENTS = {
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "Stop",
}


def normalize_event(event: dict[str, Any], user_id: str | None = None) -> dict[str, Any]:
    event_type = str(event.get("event") or event.get("hook_event_name") or "")
    if event_type not in SUPPORTED_EVENTS:
        raise ValueError(f"unsupported event: {event_type}")

    session_id = str(event.get("session_id") or "unknown")
    resolved_user_id = user_id or f"codex:{session_id}"

    payload = {
        "session_id": session_id,
        "user_id": resolved_user_id,
        "source": "codex",
        "input": "",
        "output": "",
        "metadata": {
            "event_type": event_type,
            "raw_event": copy.deepcopy(event),
        },
    }

    if event_type == "UserPromptSubmit":
        payload["input"] = str(event.get("prompt") or "")
    elif event_type == "PreToolUse":
        payload["input"] = _tool_summary(event)
    elif event_type == "PostToolUse":
        payload["input"] = _tool_summary(event)
        payload["output"] = _tool_output_summary(event)
    elif event_type == "Stop":
        payload["output"] = str(
            event.get("reason")
            or event.get("last_assistant_message")
            or ""
        )

    return payload


def extract_transcript_path(event: dict[str, Any]) -> str:
    return str(event.get("transcript_path") or "")


def build_transcript_snapshot_payload(
    session_id: str,
    user_id: str,
    transcript_path: str | Path,
) -> dict[str, Any]:
    transcript_path = Path(transcript_path)
    transcript_bytes = transcript_path.read_bytes()
    raw_transcript_jsonl = transcript_bytes.decode("utf-8")

    return {
        "session_id": session_id,
        "user_id": user_id,
        "source": "codex",
        "input": "",
        "output": "transcript snapshot archived",
        "metadata": {
            "event_type": "TranscriptSnapshot",
            "origin_event_type": "Stop",
            "transcript_path": str(transcript_path),
            "transcript_sha256": hashlib.sha256(transcript_bytes).hexdigest(),
            "transcript_bytes": len(transcript_bytes),
            "transcript_line_count": len(raw_transcript_jsonl.splitlines()),
            "raw_transcript_jsonl": raw_transcript_jsonl,
        },
    }


def _tool_summary(event: dict[str, Any]) -> str:
    tool_name = str(event.get("tool_name") or "unknown")
    tool_input = event.get("tool_input")
    if isinstance(tool_input, dict):
        command = tool_input.get("command")
        if command:
            return f"{tool_name}: {command}"
        return f"{tool_name}: {json.dumps(tool_input, ensure_ascii=False, sort_keys=True)}"
    if tool_input is None:
        return tool_name
    return f"{tool_name}: {tool_input}"


def _tool_output_summary(event: dict[str, Any]) -> str:
    tool_output = event.get("tool_output", event.get("tool_response"))
    if isinstance(tool_output, dict):
        stdout = tool_output.get("stdout")
        if stdout:
            return str(stdout)
        return json.dumps(tool_output, ensure_ascii=False, sort_keys=True)
    if tool_output is None:
        return ""
    return str(tool_output)
