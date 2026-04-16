from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from capitok.client_config import load_api_client_config

ROOT_DIR = Path(__file__).resolve().parents[2]


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _truncate(text: Any, width: int = 88) -> str:
    value = _as_text(text).strip()
    if len(value) <= width:
        return value
    return value[: max(0, width - 1)].rstrip() + "…"


def _runtime_config() -> tuple[str, str, float]:
    config = load_api_client_config()
    if not config.api_url:
        raise RuntimeError("Capitok API URL is not configured")
    if not config.api_key:
        raise RuntimeError("Capitok API key is not configured")
    return config.api_url.rstrip("/"), config.api_key, float(config.timeout)


def _request_json(
    method: str,
    path: str,
    *,
    query: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
) -> Any:
    api_url, api_key, timeout = _runtime_config()
    url = api_url + path
    if query:
        items: list[tuple[str, str]] = []
        for key, value in query.items():
            if value is None:
                continue
            items.append((key, str(value)))
        if items:
            url += "?" + urlencode(items)

    headers = {
        "Accept": "application/json",
        "X-API-Key": api_key,
    }
    payload = None
    if data is not None:
        payload = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(url, data=payload, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            if not raw.strip():
                return None
            return json.loads(raw)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace").strip()
        message = body or exc.reason or "HTTP error"
        raise RuntimeError(f"{exc.code} {message}") from exc
    except URLError as exc:
        raise RuntimeError(f"Unable to reach Capitok at {api_url}: {exc.reason}") from exc


def _collection(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        value = payload.get("items")
        if isinstance(value, list):
            return value
    return []


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _format_session_row(item: dict[str, Any]) -> str:
    preview = _truncate(item.get("preview", ""))
    source = _as_text(item.get("source") or "-")
    updated_at = _as_text(item.get("updated_at") or "-")
    session_id = _as_text(item.get("session_id") or "-")
    record_count = item.get("record_count")
    suffix = f" ({record_count})" if record_count is not None else ""
    return f"{preview}{suffix} | {source} | {updated_at} | {session_id}"


def _format_record_row(item: dict[str, Any]) -> str:
    timestamp = _as_text(item.get("created_at") or "-")
    source = _as_text(item.get("source") or "-")
    session_id = _as_text(item.get("session_id") or "-")
    preview = _truncate(item.get("input") or item.get("output") or "")
    event = _as_text(item.get("event") or "-")
    return f"{timestamp} | {source} | {session_id} | {event} | {preview}"


def _print_search(payload: Any) -> None:
    items = _collection(payload)
    if not items:
        print("No matches.")
        return
    for item in items:
        if not isinstance(item, dict):
            print(_truncate(item))
            continue
        timestamp = _as_text(item.get("created_at") or "-")
        session_id = _as_text(item.get("session_id") or "-")
        score = _as_text(item.get("score") or "-")
        text = _truncate(item.get("text") or "")
        print(f"{timestamp} | {session_id} | score={score} | {text}")


def _print_sessions(payload: Any, view: str) -> None:
    items = _collection(payload)
    if not items:
        print("No sessions found.")
        return
    formatter = _format_session_row if view == "sessions" else _format_record_row
    for item in items:
        if isinstance(item, dict):
            print(formatter(item))
        else:
            print(_truncate(item))


def _print_session_detail(payload: Any) -> None:
    if not isinstance(payload, dict):
        print(_truncate(payload))
        return

    session_id = _as_text(payload.get("session_id") or "-")
    source = _as_text(payload.get("source") or "-")
    record_count = payload.get("record_count")
    started_at = _as_text(payload.get("started_at") or "-")
    updated_at = _as_text(payload.get("updated_at") or "-")
    print(f"Session: {session_id}")
    print(f"Source: {source}")
    print(f"Started: {started_at}")
    print(f"Updated: {updated_at}")
    if record_count is not None:
        print(f"Records: {record_count}")

    timeline = _collection(payload.get("items") or [])
    if timeline:
        print("Timeline:")
        for item in timeline:
            if not isinstance(item, dict):
                print(f"- {_truncate(item)}")
                continue
            timestamp = _as_text(item.get("created_at") or "-")
            event = _as_text(item.get("metadata", {}).get("event_type") or "-")
            input_excerpt = _truncate(item.get("input") or "")
            output_excerpt = _truncate(item.get("output") or "")
            print(f"- {timestamp} | {event}")
            if input_excerpt:
                print(f"  IN: {input_excerpt}")
            if output_excerpt:
                print(f"  OUT: {output_excerpt}")
        return


def cmd_health(_args: argparse.Namespace) -> int:
    payload = _request_json("GET", "/health")
    if not isinstance(payload, dict):
        print("unknown")
        return 1

    status = _as_text(payload.get("status") or "unknown")
    ok = payload.get("ok")
    env = _as_text(payload.get("env") or "").strip()
    suffix = f" ({env})" if env else ""
    print(f"{status}{suffix}")

    if ok is False:
        return 1
    if ok is None and status != "ok":
        return 1
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    payload = _request_json("GET", "/v1/search", query={"query": args.query, "top_k": args.top_k})
    _print_search(payload)
    return 0


def cmd_sessions_list(args: argparse.Namespace) -> int:
    payload = _request_json(
        "GET",
        "/v1/sessions",
        query={"limit": args.limit, "view": args.view, "source": args.source},
    )
    if args.json:
        _print_json(payload)
    else:
        _print_sessions(payload, args.view)
    return 0


def cmd_sessions_show(args: argparse.Namespace) -> int:
    payload = _request_json("GET", f"/v1/sessions/{quote(args.session_id, safe='')}", query={"source": args.source})
    if args.json or args.raw:
        _print_json(payload)
    else:
        _print_session_detail(payload)
    return 0


def _run_install_script(script_name: str) -> int:
    script_path = ROOT_DIR / "scripts" / script_name
    if not script_path.exists():
        raise RuntimeError(f"{script_name} is only available from a Capitok source checkout")
    completed = subprocess.run(["bash", str(script_path)], cwd=ROOT_DIR)
    return completed.returncode


def cmd_codex_enable(_args: argparse.Namespace) -> int:
    return _run_install_script("install-codex-hook.sh")


def cmd_hermes_enable(_args: argparse.Namespace) -> int:
    return _run_install_script("install-hermes-plugin.sh")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="capitok",
        description="Thin session-first CLI for Capitok.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    health_parser = subparsers.add_parser("health", help="Check the Capitok API health.")
    health_parser.set_defaults(func=cmd_health)

    search_parser = subparsers.add_parser("search", help="Search archived Capitok content.")
    search_parser.add_argument("query", help="Search query.")
    search_parser.add_argument("--top-k", type=int, default=10, dest="top_k", help="Maximum results to return.")
    search_parser.set_defaults(func=cmd_search)

    sessions_parser = subparsers.add_parser("sessions", help="Inspect archived sessions.")
    sessions_subparsers = sessions_parser.add_subparsers(dest="sessions_command", required=True)

    sessions_list = sessions_subparsers.add_parser("list", help="List recent sessions or raw records.")
    sessions_list.add_argument("--limit", type=int, default=20, help="Maximum rows to return.")
    sessions_list.add_argument(
        "--view",
        choices=("sessions", "records"),
        default="sessions",
        help="Switch between session summary and raw record views.",
    )
    sessions_list.add_argument("--source", help="Restrict results to a source/runtime.")
    sessions_list.add_argument("--json", action="store_true", help="Emit JSON instead of human-readable text.")
    sessions_list.set_defaults(func=cmd_sessions_list)

    sessions_show = sessions_subparsers.add_parser("show", help="Show one session timeline.")
    sessions_show.add_argument("session_id", help="Session identifier.")
    sessions_show.add_argument("--source", help="Restrict lookup to a source/runtime.")
    sessions_show.add_argument("--raw", action="store_true", help="Print the raw JSON payload.")
    sessions_show.add_argument("--json", action="store_true", help="Print JSON output.")
    sessions_show.set_defaults(func=cmd_sessions_show)

    codex_parser = subparsers.add_parser("codex", help="Codex integration commands.")
    codex_subparsers = codex_parser.add_subparsers(dest="codex_command", required=True)
    codex_enable = codex_subparsers.add_parser("enable", help="Enable Capitok Codex hooks.")
    codex_enable.set_defaults(func=cmd_codex_enable)

    hermes_parser = subparsers.add_parser("hermes", help="Hermes integration commands.")
    hermes_subparsers = hermes_parser.add_subparsers(dest="hermes_command", required=True)
    hermes_enable = hermes_subparsers.add_parser("enable", help="Enable the Capitok Hermes plugin.")
    hermes_enable.set_defaults(func=cmd_hermes_enable)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except RuntimeError as exc:
        parser.exit(1, f"error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
