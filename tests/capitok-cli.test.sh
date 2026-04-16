#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
SERVER_PID=""
FAKE_BASH_DIR="$TMP_DIR/fake-bin"
REQUEST_LOG="$TMP_DIR/requests.log"
PORT_FILE="$TMP_DIR/port"
FAKE_BASH_LOG="$TMP_DIR/bash.log"

cleanup() {
  if [[ -n "$SERVER_PID" ]]; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
  fi
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

python3 - "$TMP_DIR" <<'PY' &
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

root = sys.argv[1]
request_log = os.path.join(root, "requests.log")
port_file = os.path.join(root, "port")


def write_response(handler, status, payload):
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def do_GET(self):
        if self.headers.get("X-API-Key") != "test-key":
            write_response(self, 401, {"detail": "missing or invalid api key"})
            return

        parsed = urlparse(self.path)
        with open(request_log, "a", encoding="utf-8") as fh:
            fh.write(f"{self.command} {parsed.path}?{parsed.query}\n")

        query = parse_qs(parsed.query)
        if parsed.path == "/health":
            write_response(self, 200, {"ok": True, "status": "ok"})
            return

        if parsed.path == "/v1/search":
            if query.get("query") != ["codex"]:
                write_response(self, 400, {"detail": "unexpected query"})
                return
            if query.get("top_k") != ["2"]:
                write_response(self, 400, {"detail": "unexpected top_k"})
                return
            write_response(
                self,
                200,
                {
                    "items": [
                        {
                            "session_id": "search-session",
                            "created_at": "2026-04-15T09:00:00Z",
                            "score": 0.91,
                            "text": "search hit one",
                        }
                    ]
                },
            )
            return

        if parsed.path == "/v1/sessions":
            view = query.get("view", ["sessions"])[0]
            source = query.get("source", [None])[0]
            if view == "records":
                if source == "codex":
                    write_response(
                    self,
                    200,
                    {
                        "view": "records",
                        "items": [
                            {
                                "session_id": "shared-session",
                                "source": "codex",
                                "created_at": "2026-04-15T10:00:00Z",
                                "event": "UserPromptSubmit",
                                "input": "First user message that should be truncated because it is intentionally very long for the CLI preview assertion.",
                                "output": "",
                            },
                            {
                                "session_id": "shared-session",
                                "source": "codex",
                                "created_at": "2026-04-15T10:01:00Z",
                                "event": "Stop",
                                "input": "",
                                "output": "codex final response",
                            },
                        ],
                    },
                )
                    return
                write_response(
                    self,
                    200,
                {
                    "view": "records",
                    "items": [
                        {
                            "session_id": "shared-session",
                            "source": "hermes",
                            "created_at": "2026-04-15T11:00:00Z",
                            "event": "UserPromptSubmit",
                            "input": "Hermes raw record",
                            "output": "",
                        }
                    ],
                },
            )
                return

            if source == "codex":
                write_response(
                    self,
                    200,
                    {
                        "view": "sessions",
                        "items": [
                            {
                                "session_id": "shared-session",
                                "source": "codex",
                                "updated_at": "2026-04-15T10:01:00Z",
                                "record_count": 2,
                                "preview": "First user message that should be truncated because it is intentionally very long for the CLI preview assertion.",
                            }
                        ],
                    },
                )
                return
            if source == "hermes":
                write_response(
                    self,
                    200,
                    {
                        "view": "sessions",
                        "items": [
                            {
                                "session_id": "shared-session",
                                "source": "hermes",
                                "updated_at": "2026-04-15T11:00:00Z",
                                "record_count": 1,
                                "preview": "Hermes summary preview",
                            }
                        ],
                    },
                )
                return
            write_response(
                self,
                200,
                {
                    "view": "sessions",
                    "items": [
                        {
                            "session_id": "shared-session",
                            "source": "codex",
                            "updated_at": "2026-04-15T10:01:00Z",
                            "record_count": 2,
                            "preview": "First user message that should be truncated because it is intentionally very long for the CLI preview assertion.",
                        },
                        {
                            "session_id": "shared-session",
                            "source": "hermes",
                            "updated_at": "2026-04-15T11:00:00Z",
                            "record_count": 1,
                            "preview": "Hermes summary preview",
                        },
                    ],
                },
            )
            return

        if parsed.path == "/v1/sessions/shared-session":
            source = query.get("source", [None])[0]
            if source is None:
                write_response(
                    self,
                    409,
                    {"detail": "session_id shared-session matches multiple sources; pass source"},
                )
                return
            if source == "codex":
                write_response(
                    self,
                    200,
                    {
                        "session_id": "shared-session",
                        "source": "codex",
                        "started_at": "2026-04-15T10:00:00Z",
                        "updated_at": "2026-04-15T10:01:00Z",
                        "record_count": 2,
                        "items": [
                            {
                                "created_at": "2026-04-15T10:00:00Z",
                                "metadata": {"event_type": "UserPromptSubmit"},
                                "input": "First user message that should be truncated because it is intentionally very long for the CLI preview assertion.",
                                "output": "",
                            },
                            {
                                "created_at": "2026-04-15T10:01:00Z",
                                "metadata": {"event_type": "Stop"},
                                "input": "",
                                "output": "codex final response",
                            },
                        ],
                    },
                )
                return
            if source == "hermes":
                write_response(
                    self,
                    200,
                    {
                        "session_id": "shared-session",
                        "source": "hermes",
                        "started_at": "2026-04-15T11:00:00Z",
                        "updated_at": "2026-04-15T11:00:00Z",
                        "record_count": 1,
                        "items": [
                            {
                                "created_at": "2026-04-15T11:00:00Z",
                                "metadata": {"event_type": "UserPromptSubmit"},
                                "input": "Hermes detail response",
                                "output": "",
                            }
                        ],
                    },
                )
                return
            write_response(self, 404, {"detail": "not found"})
            return

        if parsed.path == "/v1/sessions/unique-session":
            source = query.get("source", [None])[0]
            if source == "codex":
                write_response(
                    self,
                    200,
                    {
                        "session_id": "unique-session",
                        "source": "codex",
                        "record_count": 1,
                        "timeline": [
                            {
                                "timestamp": "2026-04-15T12:00:00Z",
                                "event": "Stop",
                                "text": "unique session detail",
                            }
                        ],
                    },
                )
                return
            write_response(self, 404, {"detail": "not found"})
            return

        write_response(self, 404, {"detail": "not found"})


server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
with open(port_file, "w", encoding="utf-8") as fh:
    fh.write(str(server.server_address[1]))
server.serve_forever()
PY
SERVER_PID=$!

while [[ ! -s "$PORT_FILE" ]]; do
  sleep 0.1
done

export CAPITOK_API_URL="http://127.0.0.1:$(cat "$PORT_FILE")"
export CAPITOK_API_KEY="test-key"

run_cli() {
  uv run capitok "$@"
}

health_output="$(run_cli health)"
[[ "$health_output" == "ok" ]]

search_output="$(run_cli search codex --top-k 2)"
[[ "$search_output" == *"search hit one"* ]]
[[ "$search_output" == *"search-session"* ]]
[[ "$search_output" == *"score=0.91"* ]]

list_output="$(run_cli sessions list --limit 20)"
[[ "$list_output" == *"First user message that should be truncated because it is intentionally very long"* ]]
[[ "$list_output" == *"| codex | 2026-04-15T10:01:00Z | shared-session"* ]]
[[ "$list_output" == *"| hermes | 2026-04-15T11:00:00Z | shared-session"* ]]

records_output="$(run_cli sessions list --limit 2 --view records --source codex)"
[[ "$records_output" == *"UserPromptSubmit"* ]]
[[ "$records_output" == *"codex final response"* ]]

json_output="$(run_cli sessions list --limit 2 --source hermes --json)"
python3 - "$json_output" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
assert payload["view"] == "sessions"
assert len(payload["items"]) == 1
assert payload["items"][0]["source"] == "hermes"
PY

detail_output="$(run_cli sessions show shared-session --source codex)"
[[ "$detail_output" == *"Session: shared-session"* ]]
[[ "$detail_output" == *"Started: 2026-04-15T10:00:00Z"* ]]
[[ "$detail_output" == *"Updated: 2026-04-15T10:01:00Z"* ]]
[[ "$detail_output" == *"Timeline:"* ]]
[[ "$detail_output" == *"IN: First user message that should be truncated because it is intentionally very long"* ]]
[[ "$detail_output" == *"OUT: codex final response"* ]]
[[ "$detail_output" == *"codex final response"* ]]

detail_json="$(run_cli sessions show shared-session --source hermes --json)"
python3 - "$detail_json" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
assert payload["source"] == "hermes"
assert payload["record_count"] == 1
assert payload["items"][0]["input"] == "Hermes detail response"
PY

if run_cli sessions show shared-session >/dev/null 2>"$TMP_DIR/conflict.err"; then
  echo "expected ambiguous detail lookup to fail" >&2
  exit 1
fi
grep -q "pass source" "$TMP_DIR/conflict.err"

if run_cli sessions show shared-session --source hermes >/dev/null 2>"$TMP_DIR/mismatch.err"; then
  :
fi

PYTHONPATH=src uv run python - "$ROOT_DIR" <<'PY'
import argparse
import sys
from pathlib import Path
from unittest.mock import patch

from capitok import cli as cli_module

root_dir = Path(sys.argv[1])
calls = []


def fake_run(argv, cwd=None):
    calls.append((argv, cwd))

    class Result:
        returncode = 0

    return Result()


with patch("subprocess.run", fake_run):
    assert cli_module.main(["codex", "enable"]) == 0
    assert cli_module.main(["hermes", "enable"]) == 0

assert calls[0][0] == ["bash", str(root_dir / "scripts" / "install-codex-hook.sh")]
assert calls[0][1] == root_dir
assert calls[1][0] == ["bash", str(root_dir / "scripts" / "install-hermes-plugin.sh")]
assert calls[1][1] == root_dir
PY

grep -q "GET /health?" "$REQUEST_LOG"
grep -q "GET /v1/search?query=codex&top_k=2" "$REQUEST_LOG"
grep -q "GET /v1/sessions?limit=20&view=sessions" "$REQUEST_LOG"
grep -q "GET /v1/sessions?limit=2&view=records&source=codex" "$REQUEST_LOG"
grep -q "GET /v1/sessions/shared-session?source=codex" "$REQUEST_LOG"

PYTHONPATH=src uv run python - <<'PY'
import argparse

from capitok.cli import cmd_health


class BrokenHealth:
    def __call__(self, _method, _path, **_kwargs):
        return {"ok": False, "status": "down"}


from capitok import cli as cli_module

original = cli_module._request_json
cli_module._request_json = BrokenHealth()
try:
    assert cmd_health(argparse.Namespace()) == 1
finally:
    cli_module._request_json = original
PY
