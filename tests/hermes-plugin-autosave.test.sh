#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"$HOME/.hermes/hermes-agent/venv/bin/python3" - <<'PY'
import importlib.util
from pathlib import Path

plugin_path = Path.cwd() / "integrations" / "hermes" / "__init__.py"
spec = importlib.util.spec_from_file_location("capitok_plugin_test", plugin_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

calls = {"ingest": 0}

class StubClient:
    def set_ids(self, session_id, user_id):
        self.session_id = session_id
        self.user_id = user_id
    def ingest(self, user_input, assistant_output, metadata=None):
        calls["ingest"] += 1
        return {"status": "success", "result": {"status": "queued"}}

module._client = StubClient()
module._config = {"auto_save": True}
module._enabled = True

module.on_post_llm_call(
    session_id="autosave-test-session",
    user_message="autosave test input",
    assistant_response="autosave test output",
    platform="cli",
)

if calls["ingest"] != 1:
    raise SystemExit(f"expected synchronous ingest call, got {calls['ingest']}")

print("capitok plugin autosave runs synchronously")
PY
