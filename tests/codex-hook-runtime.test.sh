#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$repo_root"

uv run --no-project --isolated python - <<'PY'
import io
import json
import os
from pathlib import Path
from unittest.mock import patch

from integrations.codex import hook_runtime

event = {
    "event": "UserPromptSubmit",
    "session_id": "runtime-session",
    "prompt": "archive this prompt",
}

captured = {}


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def fake_urlopen(request, timeout):
    captured["url"] = request.full_url
    captured["body"] = request.data.decode("utf-8")
    captured["headers"] = dict(request.header_items())
    captured["timeout"] = timeout
    return FakeResponse()


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
    with patch("sys.stdin", io.StringIO(json.dumps(event))):
        with patch("urllib.request.urlopen", fake_urlopen):
            code = hook_runtime.main()
finally:
    if original is None:
        repo_env.unlink(missing_ok=True)
    else:
        repo_env.write_text(original)

assert code == 0
assert captured["url"] == "http://127.0.0.1:8000/v1/ingest"
assert json.loads(captured["body"])["input"] == "archive this prompt"
headers = {key.lower(): value for key, value in captured["headers"].items()}
assert headers["x-api-key"] == "test-key"
PY
