#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

hermes_home="$tmpdir/.hermes"
plugin_dir="$hermes_home/plugins/capitok"
mkdir -p "$hermes_home/plugins"
cp -R "$repo_root/integrations/hermes" "$plugin_dir"

cat > "$hermes_home/config.yaml" <<'EOF'
plugins:
  capitok:
    enabled: true
    api_url: http://localhost:8000
    api_key: test-key
    auto_save: true
    timeout: 5.0
EOF

output="$(TEST_HERMES_HOME="$hermes_home" "$HOME/.hermes/hermes-agent/venv/bin/python3" - <<'PY'
import json
import os

os.environ["HERMES_HOME"] = os.environ["TEST_HERMES_HOME"]

from hermes_cli.plugins import PluginManager

mgr = PluginManager()
mgr.discover_and_load()
plugins = {item["name"]: item for item in mgr.list_plugins()}
capitok = plugins.get("capitok")
loaded = mgr._plugins.get("capitok")
print(json.dumps({
    "found": capitok is not None,
    "enabled": capitok.get("enabled") if capitok else None,
    "error": capitok.get("error") if capitok else None,
    "hooks": loaded.hooks_registered if loaded else None,
    "tools": loaded.tools_registered if loaded else None,
}, ensure_ascii=False))
PY
)"

if [[ "$output" != *'"found": true'* ]]; then
  echo "expected capitok plugin to be discovered"
  echo "$output"
  exit 1
fi

if [[ "$output" != *'"enabled": true'* ]]; then
  echo "expected capitok plugin to load successfully"
  echo "$output"
  exit 1
fi

if [[ "$output" != *'"error": null'* ]]; then
  echo "expected capitok plugin load error to be null"
  echo "$output"
  exit 1
fi

if [[ "$output" != *'post_llm_call'* ]]; then
  echo "expected capitok plugin to register a supported turn hook"
  echo "$output"
  exit 1
fi

if [[ "$output" != *'capitok_recall'* || "$output" != *'capitok_save'* ]]; then
  echo "expected capitok plugin tools to register"
  echo "$output"
  exit 1
fi

echo "capitok plugin loads under current Hermes plugin API"
