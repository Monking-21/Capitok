from __future__ import annotations

import sys
import json
from pathlib import Path
import urllib.error
import urllib.request

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from integrations.codex.config import load_config
from integrations.codex.payloads import normalize_event


def _post_ingest(api_url: str, api_key: str, payload: dict[str, object], timeout: float) -> None:
    request = urllib.request.Request(
        f"{api_url}/v1/ingest",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout):
        return


def main() -> int:
    config = load_config()
    if not config.api_key:
        print("Capitok Codex hook: CAPITOK_API_KEY is required", file=sys.stderr)
        return 1

    try:
        event = json.loads(sys.stdin.read())
        payload = normalize_event(event, user_id=config.user_id)
        _post_ingest(config.api_url, config.api_key, payload, config.timeout)
        return 0
    except urllib.error.HTTPError as exc:
        print(f"Capitok Codex hook ingest failed: HTTP {exc.code}", file=sys.stderr)
        return 0
    except Exception as exc:
        print(f"Capitok Codex hook error: {exc}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
