from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _load_repo_env() -> dict[str, str]:
    repo_root = _repo_root()
    values = _parse_env_file(repo_root / ".env.dev")
    values.update(_parse_env_file(repo_root / ".env"))
    return values


def _resolve_api_url(env_values: dict[str, str]) -> str:
    explicit = os.environ.get("CAPITOK_API_URL")
    if explicit:
        return explicit.rstrip("/")

    host = env_values.get("APP_HOST", "127.0.0.1")
    port = env_values.get("APP_PORT", "8000")
    if host in {"0.0.0.0", "::"}:
        host = "127.0.0.1"
    return f"http://{host}:{port}".rstrip("/")


def _resolve_api_key(env_values: dict[str, str]) -> str:
    explicit = os.environ.get("CAPITOK_API_KEY")
    if explicit:
        return explicit

    raw_keys = env_values.get("AUTH_API_KEYS_JSON", "")
    if not raw_keys:
        return ""

    try:
        parsed = json.loads(raw_keys)
    except json.JSONDecodeError:
        return ""

    if not isinstance(parsed, dict) or len(parsed) != 1:
        return ""

    only_key = next(iter(parsed.keys()), "")
    return str(only_key)


@dataclass(frozen=True)
class ApiClientConfig:
    api_url: str
    api_key: str
    timeout: float


def load_api_client_config() -> ApiClientConfig:
    env_values = _load_repo_env()
    return ApiClientConfig(
        api_url=_resolve_api_url(env_values),
        api_key=_resolve_api_key(env_values),
        timeout=float(os.environ.get("CAPITOK_TIMEOUT", "5.0")),
    )
