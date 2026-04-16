from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from capitok.client_config import load_api_client_config
except ModuleNotFoundError:
    src_dir = Path(__file__).resolve().parents[2] / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    from capitok.client_config import load_api_client_config


@dataclass(frozen=True)
class CodexHookConfig:
    api_url: str
    api_key: str
    timeout: float
    mode: str
    scope: str
    user_id: str | None


def load_config() -> CodexHookConfig:
    client_config = load_api_client_config()
    return CodexHookConfig(
        api_url=client_config.api_url,
        api_key=client_config.api_key,
        timeout=client_config.timeout,
        mode=os.environ.get("CAPITOK_CODEX_MODE", "basic"),
        scope=os.environ.get("CAPITOK_CODEX_SCOPE", "global"),
        user_id=os.environ.get("CAPITOK_CODEX_USER_ID") or None,
    )
