#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$repo_root"

uv run --no-project --isolated python - <<'PY'
import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from integrations.codex import hook_runtime

class FakeResponse:
    def __init__(self, body=""):
        self._body = body.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._body


def run_case(event, *, existing=False):
    captured = {"requests": []}

    def fake_urlopen(request, timeout):
        body = request.data.decode("utf-8") if request.data else ""
        captured["requests"].append(
            {
                "url": request.full_url,
                "body": body,
                "headers": dict(request.header_items()),
                "timeout": timeout,
                "method": request.get_method(),
            }
        )
        if request.full_url.startswith("http://127.0.0.1:8000/v1/transcript-snapshots/exists"):
            return FakeResponse(json.dumps({"exists": existing}))
        return FakeResponse()

    with patch("sys.stdin", io.StringIO(json.dumps(event))):
        with patch("urllib.request.urlopen", fake_urlopen):
            code = hook_runtime.main()
    return code, captured


for key in ("CAPITOK_API_URL", "CAPITOK_API_KEY"):
    os.environ.pop(key, None)

repo_env = Path(".env")
original = repo_env.read_text() if repo_env.exists() else None
repo_env.write_text(
    "APP_HOST=0.0.0.0\n"
    "APP_PORT=8000\n"
    'AUTH_API_KEYS_JSON={"test-key":{"tenant_id":"demo","principal_id":"demo","scopes":["ingest","search"]}}\n'
)

try:
    prompt_event = {
        "event": "UserPromptSubmit",
        "session_id": "runtime-session",
        "prompt": "archive this prompt",
    }
    code, captured = run_case(prompt_event)

    assert code == 0
    assert len(captured["requests"]) == 1
    assert captured["requests"][0]["url"] == "http://127.0.0.1:8000/v1/ingest"
    assert json.loads(captured["requests"][0]["body"])["input"] == "archive this prompt"
    headers = {key.lower(): value for key, value in captured["requests"][0]["headers"].items()}
    assert headers["x-api-key"] == "test-key"

    with TemporaryDirectory() as tmpdir:
        transcript_path = Path(tmpdir) / "session.jsonl"
        transcript_text = (
            '{"type":"session_meta"}\n'
            '{"type":"event_msg","payload":{"type":"agent_message","message":"done"}}\n'
        )
        transcript_path.write_text(transcript_text, encoding="utf-8")

        stop_event = {
            "hook_event_name": "Stop",
            "session_id": "runtime-session-stop",
            "last_assistant_message": "done",
            "transcript_path": str(transcript_path),
        }
        code, captured = run_case(stop_event)
        assert code == 0
        assert len(captured["requests"]) == 3
        assert json.loads(captured["requests"][0]["body"])["metadata"]["event_type"] == "Stop"
        assert captured["requests"][1]["method"] == "GET"
        assert "/v1/transcript-snapshots/exists?" in captured["requests"][1]["url"]
        transcript_payload = json.loads(captured["requests"][2]["body"])
        assert transcript_payload["metadata"]["event_type"] == "TranscriptSnapshot"
        assert transcript_payload["metadata"]["raw_transcript_jsonl"] == transcript_text

        missing_event = {
            "hook_event_name": "Stop",
            "session_id": "runtime-session-missing",
            "last_assistant_message": "done",
            "transcript_path": str(Path(tmpdir) / "missing.jsonl"),
        }
        code, captured = run_case(missing_event)
        assert code == 0
        assert len(captured["requests"]) == 1
        assert json.loads(captured["requests"][0]["body"])["metadata"]["event_type"] == "Stop"

        code, captured = run_case(stop_event, existing=True)
        assert code == 0
        assert len(captured["requests"]) == 2
        assert json.loads(captured["requests"][0]["body"])["metadata"]["event_type"] == "Stop"
        assert captured["requests"][1]["method"] == "GET"
finally:
    if original is None:
        repo_env.unlink(missing_ok=True)
    else:
        repo_env.write_text(original)
PY
