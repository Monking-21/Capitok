#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_dir="$repo_root/integrations/hermes"
hermes_home="${HERMES_HOME:-$HOME/.hermes}"
plugin_dir="${CAPITOK_HERMES_PLUGIN_DIR:-$hermes_home/plugins/capitok}"
config_file="${CAPITOK_HERMES_CONFIG_FILE:-$hermes_home/config.yaml}"
api_url="${CAPITOK_API_URL:-}"
api_key="${CAPITOK_API_KEY:-}"
auto_save="${CAPITOK_AUTO_SAVE:-}"
timeout="${CAPITOK_TIMEOUT:-}"
recommended_hermes_version="${CAPITOK_RECOMMENDED_HERMES_VERSION:-0.9.0}"

warn() {
  echo "Warning: $*" >&2
}

version_lt() {
  local left="$1"
  local right="$2"
  local first

  first="$(printf '%s\n%s\n' "$left" "$right" | sort -V | head -n1)"
  [[ "$first" == "$left" && "$left" != "$right" ]]
}

detect_hermes_version() {
  local output

  if ! command -v hermes >/dev/null 2>&1; then
    warn "Hermes CLI was not found in PATH. Capitok installed the plugin files, but cannot verify Hermes compatibility."
    warn "If the plugin does not load or behave correctly, check your Hermes installation first."
    return 0
  fi

  if ! output="$(hermes --version 2>/dev/null)"; then
    if ! output="$(hermes version 2>/dev/null)"; then
      warn "Hermes is installed, but its version could not be detected automatically."
      warn "The plugin was still installed. If it does not work correctly, your Hermes version may be incompatible."
      return 0
    fi
  fi

  if [[ "$output" =~ v([0-9]+(\.[0-9]+)+) ]]; then
    hermes_version="${BASH_REMATCH[1]}"
    if version_lt "$hermes_version" "$recommended_hermes_version"; then
      warn "Detected Hermes $hermes_version. Capitok currently recommends Hermes $recommended_hermes_version or newer."
      warn "Installation will continue, but this Hermes version may not be fully compatible and the plugin may not work correctly."
    fi
  else
    warn "Hermes version output was detected but could not be parsed:"
    warn "$output"
    warn "Installation will continue, but plugin compatibility could not be verified."
  fi
}

read_env_value() {
  local key="$1"
  local file_path="$2"
  local line value

  [[ -f "$file_path" ]] || return 1

  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    line="${line#export }"
    if [[ "$line" == "$key="* ]]; then
      value="${line#"$key="}"
      if [[ "$value" == '"'*'"' ]]; then
        value="${value:1:${#value}-2}"
      elif [[ "$value" == "'"*"'" ]]; then
        value="${value:1:${#value}-2}"
      fi
      printf '%s\n' "$value"
      return 0
    fi
  done < "$file_path"

  return 1
}

if [[ -z "$api_url" ]]; then
  api_url="$(read_env_value CAPITOK_API_URL "$repo_root/.env" || true)"
fi
if [[ -z "$api_url" ]]; then
  api_url="$(read_env_value CAPITOK_API_URL "$repo_root/.env.dev" || true)"
fi

if [[ -z "$api_key" ]]; then
  api_key="$(read_env_value CAPITOK_API_KEY "$repo_root/.env" || true)"
fi
if [[ -z "$api_key" ]]; then
  api_key="$(read_env_value CAPITOK_API_KEY "$repo_root/.env.dev" || true)"
fi

if [[ -z "$auto_save" ]]; then
  auto_save="$(read_env_value CAPITOK_AUTO_SAVE "$repo_root/.env" || true)"
fi
if [[ -z "$auto_save" ]]; then
  auto_save="$(read_env_value CAPITOK_AUTO_SAVE "$repo_root/.env.dev" || true)"
fi
if [[ -z "$timeout" ]]; then
  timeout="$(read_env_value CAPITOK_TIMEOUT "$repo_root/.env" || true)"
fi
if [[ -z "$timeout" ]]; then
  timeout="$(read_env_value CAPITOK_TIMEOUT "$repo_root/.env.dev" || true)"
fi

api_url="${api_url:-http://localhost:8000}"
auto_save="${auto_save:-true}"
timeout="${timeout:-5.0}"

usage() {
  cat <<'EOF'
Usage:
  CAPITOK_API_URL=http://localhost:8000 CAPITOK_API_KEY=... bash scripts/install-hermes-plugin.sh

Optional environment variables:
  CAPITOK_HERMES_PLUGIN_DIR   Override Hermes plugin directory
  CAPITOK_HERMES_CONFIG_FILE  Override Hermes config file path
  CAPITOK_RECOMMENDED_HERMES_VERSION  Recommended Hermes version for warning checks
  CAPITOK_AUTO_SAVE           true/false, defaults to true
  CAPITOK_TIMEOUT             Request timeout in seconds, defaults to 5.0

The script copies integrations/hermes into the Hermes plugin directory.
It reads CAPITOK_API_URL, CAPITOK_API_KEY, CAPITOK_AUTO_SAVE, and CAPITOK_TIMEOUT
from the shell environment first, then falls back to the repo's .env or .env.dev.
If CAPITOK_API_KEY is available, it also writes or updates a Capitok plugin block
in the Hermes config file.
If Hermes is missing, too old, or its version cannot be detected, the script only
prints a warning and continues.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ ! -d "$source_dir" ]]; then
  echo "Capitok Hermes plugin source not found: $source_dir" >&2
  exit 1
fi

detect_hermes_version

mkdir -p "$(dirname "$plugin_dir")"
rm -rf "$plugin_dir"
cp -R "$source_dir" "$plugin_dir"

echo "Installed Capitok Hermes plugin to: $plugin_dir"

if [[ -z "$api_key" ]]; then
  echo "CAPITOK_API_KEY is not set, so Hermes config was not updated."
  echo "Set CAPITOK_API_KEY and rerun this script to write $config_file automatically."
  exit 0
fi

mkdir -p "$(dirname "$config_file")"

block_file="$(mktemp)"
tmp_file="$(mktemp)"

cat > "$block_file" <<EOF
  # Capitok managed block start
  capitok:
    enabled: true
    api_url: $api_url
    api_key: $api_key
    auto_save: $auto_save
    timeout: $timeout
  # Capitok managed block end
EOF

if [[ -f "$config_file" ]] && grep -q '# Capitok managed block start' "$config_file" && grep -q '# Capitok managed block end' "$config_file"; then
  awk -v block_file="$block_file" '
    BEGIN {
      while ((getline line < block_file) > 0) {
        block = block line "\n"
      }
      close(block_file)
      in_block = 0
    }
    /# Capitok managed block start/ {
      printf "%s", block
      in_block = 1
      next
    }
    in_block && /# Capitok managed block end/ {
      in_block = 0
      next
    }
    in_block {
      next
    }
    {
      print
    }
  ' "$config_file" > "$tmp_file"
  mv "$tmp_file" "$config_file"
elif [[ -f "$config_file" ]] && grep -qE '^plugins:[[:space:]]*$' "$config_file"; then
  awk -v block_file="$block_file" '
    BEGIN {
      while ((getline line < block_file) > 0) {
        block = block line "\n"
      }
      close(block_file)
      inserted = 0
    }
    {
      print
      if (!inserted && $0 ~ /^plugins:[[:space:]]*$/) {
        printf "%s", block
        inserted = 1
      }
    }
  ' "$config_file" > "$tmp_file"
  mv "$tmp_file" "$config_file"
elif [[ -f "$config_file" ]]; then
  cp "$config_file" "$tmp_file"
  if [[ -s "$tmp_file" ]]; then
    printf '\n' >> "$tmp_file"
  fi
  {
    printf 'plugins:\n'
    cat "$block_file"
  } >> "$tmp_file"
  mv "$tmp_file" "$config_file"
else
  {
    printf 'plugins:\n'
    cat "$block_file"
  } > "$config_file"
fi

rm -f "$block_file" "$tmp_file"

echo "Updated Hermes config: $config_file"
echo "Run: hermes doctor"
