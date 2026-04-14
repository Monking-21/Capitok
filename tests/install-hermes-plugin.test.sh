#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

hermes_home="$tmpdir/.hermes"
mkdir -p "$hermes_home"

cat > "$hermes_home/config.yaml" <<'EOF'
model:
  default: test-model
display:
  personality: concise
EOF

(
  cd "$repo_root"
  HERMES_HOME="$hermes_home" \
  CAPITOK_API_URL="http://localhost:8000" \
  CAPITOK_API_KEY="test-key" \
  CAPITOK_AUTO_SAVE="true" \
  CAPITOK_TIMEOUT="5.0" \
  bash scripts/install-hermes-plugin.sh >/dev/null
)

if ! grep -q '^model:$' "$hermes_home/config.yaml"; then
  echo "expected existing config to be preserved"
  exit 1
fi

if ! grep -q '^plugins:$' "$hermes_home/config.yaml"; then
  echo "expected plugins section to be added"
  exit 1
fi

if ! grep -q '^  capitok:$' "$hermes_home/config.yaml"; then
  echo "expected capitok plugin block to be added"
  exit 1
fi

echo "install-hermes-plugin preserves config and adds plugin block"
