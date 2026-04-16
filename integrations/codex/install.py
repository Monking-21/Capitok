from __future__ import annotations

import json
import re
from pathlib import Path


CONFIG_LINE = "codex_hooks = true\n"
_CODEX_HOOKS_RE = re.compile(r"^\s*codex_hooks\s*=\s*(true|false)\s*(?:#.*)?$")
_FEATURES_SECTION_RE = re.compile(r"^\s*\[features\]\s*$")


def _codex_home() -> Path:
    return Path.home() / ".codex"


def _write_config(path: Path) -> None:
    existing = path.read_text() if path.exists() else ""
    lines = existing.splitlines(keepends=True)
    cleaned_lines: list[str] = []
    in_features = False
    features_seen = False
    inserted = False

    for line in lines:
        if _CODEX_HOOKS_RE.match(line.split("#", 1)[0].rstrip()):
            continue

        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_features and not inserted:
                cleaned_lines.append(CONFIG_LINE)
                inserted = True
            in_features = bool(_FEATURES_SECTION_RE.match(stripped))
            if in_features:
                features_seen = True
            cleaned_lines.append(line)
            continue

        cleaned_lines.append(line)

    if features_seen:
        if in_features and not inserted:
            if cleaned_lines and not cleaned_lines[-1].endswith("\n"):
                cleaned_lines[-1] = cleaned_lines[-1] + "\n"
            cleaned_lines.append(CONFIG_LINE)
    else:
        if cleaned_lines and not cleaned_lines[-1].endswith("\n"):
            cleaned_lines[-1] = cleaned_lines[-1] + "\n"
        if cleaned_lines and cleaned_lines[-1] != "\n":
            cleaned_lines.append("\n")
        cleaned_lines.append("[features]\n")
        cleaned_lines.append(CONFIG_LINE)

    path.write_text("".join(cleaned_lines))


def _write_hooks(path: Path, repo_root: Path) -> None:
    hook_runtime = repo_root / "integrations" / "codex" / "hook_runtime.py"
    command = f'uv run python "{hook_runtime}"'
    capitok_hooks = {
        "SessionStart": [
            {
                "matcher": "startup|resume",
                "hooks": [
                    {
                        "type": "command",
                        "command": command,
                    }
                ],
            }
        ],
        "UserPromptSubmit": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": command,
                    }
                ],
            }
        ],
        "PreToolUse": [
            {
                "matcher": "Bash",
                "hooks": [
                    {
                        "type": "command",
                        "command": command,
                    }
                ],
            }
        ],
        "PostToolUse": [
            {
                "matcher": "Bash",
                "hooks": [
                    {
                        "type": "command",
                        "command": command,
                    }
                ],
            }
        ],
        "Stop": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": command,
                    }
                ],
            }
        ],
    }

    raw = json.loads(path.read_text()) if path.exists() else {}
    if not isinstance(raw, dict):
        raw = {}

    legacy_event_keys = {
        "SessionStart",
        "UserPromptSubmit",
        "PreToolUse",
        "PostToolUse",
        "Stop",
    }
    hooks = raw.get("hooks")
    if not isinstance(hooks, dict):
        hooks = {}

    for key, value in list(raw.items()):
        if key in legacy_event_keys and key not in hooks:
            if isinstance(value, dict) and "command" in value:
                command_value = value["command"]
                if isinstance(command_value, list):
                    command_value = " ".join(
                        f'"{part}"' if " " in str(part) else str(part)
                        for part in command_value
                    )
                hook_entry = {
                    "hooks": [
                        {
                            "type": "command",
                            "command": str(command_value),
                        }
                    ]
                }
                if key == "SessionStart":
                    hook_entry["matcher"] = "startup|resume"
                if key in {"PreToolUse", "PostToolUse"}:
                    hook_entry["matcher"] = "Bash"
                hooks[key] = [hook_entry]
        if key != "hooks":
            raw.pop(key, None)

    hooks.update(capitok_hooks)
    raw["hooks"] = hooks
    path.write_text(json.dumps(raw, indent=2) + "\n")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    codex_home = _codex_home()
    codex_home.mkdir(parents=True, exist_ok=True)
    _write_config(codex_home / "config.toml")
    _write_hooks(codex_home / "hooks.json", repo_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
