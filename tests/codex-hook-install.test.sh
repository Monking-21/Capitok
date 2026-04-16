#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp_home="$(mktemp -d)"
tmp_uv_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_home" "$tmp_uv_dir"' EXIT

cd "$repo_root"

mkdir -p "$tmp_home/.codex"
cat > "$tmp_home/.codex/config.toml" <<'EOF'
# codex_hooks = true
model = "gpt-5"
EOF

cat > "$tmp_home/.codex/hooks.json" <<'EOF'
{
  "Stop": {
    "command": ["old", "command"]
  }
}
EOF

HOME="$tmp_home" uv run --no-project --isolated python - <<'PY'
import json
import os
import subprocess
import tempfile
from pathlib import Path

from integrations.codex import install

assert install.main() == 0

config_toml = Path.home() / ".codex" / "config.toml"
hooks_json = Path.home() / ".codex" / "hooks.json"
repo_root = Path.cwd()
runtime = str(repo_root / "integrations" / "codex" / "hook_runtime.py")

assert config_toml.exists()
assert hooks_json.exists()

config = config_toml.read_text()
assert "model = \"gpt-5\"" in config
assert "[features]" in config
assert "codex_hooks = true" in config
assert "# codex_hooks = true" in config

hooks = json.loads(hooks_json.read_text())
assert list(hooks.keys()) == ["hooks"]
for event in (
    "UserPromptSubmit",
    "SessionStart",
    "PreToolUse",
    "PostToolUse",
    "Stop",
):
    entry = hooks["hooks"][event][0]
    command = entry["hooks"][0]["command"]
    assert command == f'uv run python "{runtime}"'

assert hooks["hooks"]["SessionStart"][0]["matcher"] == "startup|resume"
assert hooks["hooks"]["PreToolUse"][0]["matcher"] == "Bash"
assert hooks["hooks"]["PostToolUse"][0]["matcher"] == "Bash"

with tempfile.TemporaryDirectory() as other_cwd:
    result = subprocess.run(
        hooks["hooks"]["Stop"][0]["hooks"][0]["command"],
        cwd=other_cwd,
        input=json.dumps(
            {
                "event": "Stop",
                "session_id": "installed-command-session",
                "reason": "completed",
            }
        ),
        text=True,
        capture_output=True,
        shell=True,
        env={
            **os.environ,
            "HOME": str(Path.home()),
            "CAPITOK_API_URL": "http://127.0.0.1:9",
            "CAPITOK_API_KEY": "test-key",
        },
        check=False,
    )

assert result.returncode == 0, result.stderr
assert "ModuleNotFoundError" not in result.stderr
assert "Capitok Codex hook error:" in result.stderr
PY

cat > "$tmp_uv_dir/uv" <<EOF
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "\$PWD" > "$tmp_uv_dir/pwd.log"
printf '%s\n' "\$*" > "$tmp_uv_dir/args.log"
EOF
chmod +x "$tmp_uv_dir/uv"

PATH="$tmp_uv_dir:$PATH" HOME="$tmp_home" bash scripts/install-codex-hook.sh

test "$(cat "$tmp_uv_dir/pwd.log")" = "$repo_root"
test "$(cat "$tmp_uv_dir/args.log")" = "run python integrations/codex/install.py"
