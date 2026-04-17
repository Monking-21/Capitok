from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlencode

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from integrations.codex.config import load_config
from integrations.codex.payloads import (
    build_transcript_snapshot_payload,
    extract_transcript_path,
    normalize_event,
)


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


def _transcript_snapshot_exists(
    api_url: str,
    api_key: str,
    session_id: str,
    source: str,
    transcript_sha256: str,
    timeout: float,
) -> bool:
    request = urllib.request.Request(
        f"{api_url}/v1/transcript-snapshots/exists?{urlencode({'session_id': session_id, 'source': source, 'transcript_sha256': transcript_sha256})}",
        headers={
            "Accept": "application/json",
            "X-API-Key": api_key,
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return bool(payload.get("exists"))


def _maybe_archive_transcript(
    event: dict[str, object],
    payload: dict[str, object],
    *,
    api_url: str,
    api_key: str,
    timeout: float,
) -> None:
    transcript_path = extract_transcript_path(event)
    if not transcript_path:
        return

    try:
        transcript_payload = build_transcript_snapshot_payload(
            session_id=str(payload["session_id"]),
            user_id=str(payload["user_id"]),
            transcript_path=transcript_path,
        )
    except FileNotFoundError:
        print(f"Capitok Codex hook transcript missing: {transcript_path}", file=sys.stderr)
        return
    except Exception as exc:
        print(f"Capitok Codex transcript build error: {exc}", file=sys.stderr)
        return

    try:
        exists = _transcript_snapshot_exists(
            api_url=api_url,
            api_key=api_key,
            session_id=str(payload["session_id"]),
            source=str(payload["source"]),
            transcript_sha256=str(transcript_payload["metadata"]["transcript_sha256"]),
            timeout=timeout,
        )
    except Exception as exc:
        print(f"Capitok Codex transcript dedup check failed: {exc}", file=sys.stderr)
        exists = False

    if exists:
        return

    try:
        _post_ingest(api_url, api_key, transcript_payload, timeout)
    except urllib.error.HTTPError as exc:
        print(f"Capitok Codex transcript ingest failed: HTTP {exc.code}", file=sys.stderr)
    except Exception as exc:
        print(f"Capitok Codex transcript ingest error: {exc}", file=sys.stderr)


def main() -> int:
    config = load_config()
    if not config.api_key:
        print("Capitok Codex hook: CAPITOK_API_KEY is required", file=sys.stderr)
        return 1

    try:
        event = json.loads(sys.stdin.read())
        payload = normalize_event(event, user_id=config.user_id)
        _post_ingest(config.api_url, config.api_key, payload, config.timeout)
        if payload["metadata"].get("event_type") == "Stop":
            _maybe_archive_transcript(
                event,
                payload,
                api_url=config.api_url,
                api_key=config.api_key,
                timeout=config.timeout,
            )
        return 0
    except urllib.error.HTTPError as exc:
        print(f"Capitok Codex hook ingest failed: HTTP {exc.code}", file=sys.stderr)
        return 0
    except Exception as exc:
        print(f"Capitok Codex hook error: {exc}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
