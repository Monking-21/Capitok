#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$repo_root"

PYTHONPATH=src uv run python - <<'PY'
import copy
import json
import os
import socket
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import uvicorn

os.environ["AUTH_API_KEYS_JSON"] = (
    '{"test-key":{"tenant_id":"demo","principal_id":"demo","scopes":["ingest","search"]}}'
)

from capitok.main import app
import capitok.db as db


class FakeState:
    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.counter = 0

    def insert(self, tenant_id, principal_id, session_id, user_id, agent_id, source, content):
        self.counter += 1
        created_at = datetime(2026, 4, 15, 9, 0, 0, tzinfo=timezone.utc) + timedelta(
            seconds=self.counter
        )
        row_id = f"00000000-0000-0000-0000-{self.counter:012d}"
        self.rows.append(
            {
                "id": row_id,
                "tenant_id": tenant_id,
                "principal_id": principal_id,
                "session_id": session_id,
                "user_id": user_id,
                "agent_id": agent_id,
                "source": source,
                "content": copy.deepcopy(content),
                "created_at": created_at,
            }
        )


def _unwrap_json_param(value):
    for attr in ("obj", "adapted", "_obj"):
        if hasattr(value, attr):
            return getattr(value, attr)
    return value


class FakeCursor:
    def __init__(self, state: FakeState) -> None:
        self._state = state
        self._query = ""
        self._params = ()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self._query = query
        self._params = tuple(params or ())
        normalized = " ".join(query.split())
        if "INSERT INTO raw_chat_logs" in normalized:
            tenant_id, principal_id, session_id, user_id, agent_id, source, content = self._params
            self._state.insert(
                tenant_id,
                principal_id,
                session_id,
                user_id,
                agent_id,
                source,
                _unwrap_json_param(content),
            )

    def fetchall(self):
        normalized = " ".join(self._query.split())
        if "GROUP BY base.tenant_id" in normalized:
            tenant_id, principal_id, *rest = self._params
            source = None
            limit = None
            rest = list(rest)
            if "base.source = %s" in normalized:
                source = rest.pop(0)
            if "LIMIT %s" in normalized and rest:
                limit = rest.pop(0)

            rows = [
                row
                for row in self._state.rows
                if row["tenant_id"] == tenant_id
                and row["principal_id"] == principal_id
                and (source is None or row["source"] == source)
            ]

            grouped: dict[tuple[str, str], list[dict]] = {}
            for row in rows:
                key = (row["session_id"], row["source"])
                grouped.setdefault(key, []).append(row)

            aggregated = []
            for (session_id, source_name), group_rows in grouped.items():
                ordered = sorted(group_rows, key=lambda row: (row["created_at"], row["id"]))
                preview = ""
                for candidate in ordered:
                    preview = candidate["content"].get("input", "") or ""
                    if preview:
                        break
                aggregated.append(
                    {
                        "session_id": session_id,
                        "source": source_name,
                        "started_at": ordered[0]["created_at"],
                        "updated_at": ordered[-1]["created_at"],
                        "record_count": len(ordered),
                        "preview": preview,
                    }
                )

            aggregated.sort(
                key=lambda row: (row["updated_at"], row["started_at"], row["session_id"], row["source"]),
                reverse=True,
            )
            if limit is not None:
                aggregated = aggregated[: int(limit)]
            return aggregated

        if "FROM raw_chat_logs" not in normalized:
            return []

        tenant_id, principal_id, *rest = self._params
        source = None
        session_id = None
        limit = None

        rest = list(rest)
        if "source = %s" in normalized:
            source = rest.pop(0)
        if "session_id = %s" in normalized:
            session_id = rest.pop(0)
        if "LIMIT %s" in normalized and rest:
            limit = rest.pop(0)

        rows = [
            row
            for row in self._state.rows
            if row["tenant_id"] == tenant_id
            and row["principal_id"] == principal_id
            and (source is None or row["source"] == source)
            and (session_id is None or row["session_id"] == session_id)
        ]

        if "ORDER BY created_at DESC" in normalized:
            rows.sort(key=lambda row: (row["created_at"], row["id"]), reverse=True)
        else:
            rows.sort(key=lambda row: (row["created_at"], row["id"]))

        if limit is not None:
            rows = rows[: int(limit)]

        return [
            {
                "id": row["id"],
                "session_id": row["session_id"],
                "source": row["source"],
                "content": copy.deepcopy(row["content"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]


class FakeConnection:
    def __init__(self, state: FakeState) -> None:
        self._state = state

    def cursor(self):
        return FakeCursor(self._state)

    def commit(self):
        return None

    def close(self):
        return None


state = FakeState()


@contextmanager
def fake_get_db():
    yield FakeConnection(state)


db.get_db = fake_get_db

db.insert_raw_chat_log(
    tenant_id="demo",
    principal_id="demo",
    session_id="session-a",
    user_id="codex:session-a",
    agent_id="codex",
    source="codex",
    content={"input": "first user message for session a", "output": "assistant reply a1", "metadata": {"agent": "codex"}},
)
db.insert_raw_chat_log(
    tenant_id="demo",
    principal_id="demo",
    session_id="session-a",
    user_id="codex:session-a",
    agent_id="codex",
    source="codex",
    content={"input": "follow-up for session a", "output": "assistant reply a2", "metadata": {"agent": "codex"}},
)
db.insert_raw_chat_log(
    tenant_id="demo",
    principal_id="demo",
    session_id="session-b",
    user_id="hermes:session-b",
    agent_id="hermes",
    source="hermes",
    content={"input": "first user message for session b", "output": "assistant reply b1", "metadata": {"agent": "hermes"}},
)
long_first_message = (
    "This is a deliberately long first user message that should be truncated in the "
    "session preview because ordinary users only need a concise recognition string."
)
db.insert_raw_chat_log(
    tenant_id="demo",
    principal_id="demo",
    session_id="session-c",
    user_id="codex:session-c",
    agent_id="codex",
    source="codex",
    content={"input": long_first_message, "output": "assistant reply c1", "metadata": {"agent": "codex"}},
)
db.insert_raw_chat_log(
    tenant_id="demo",
    principal_id="demo",
    session_id="session-d",
    user_id="codex:session-d",
    agent_id="codex",
    source="codex",
    content={"input": "", "output": "", "metadata": {"agent": "codex", "event_type": "SessionStart"}},
)
db.insert_raw_chat_log(
    tenant_id="demo",
    principal_id="demo",
    session_id="session-d",
    user_id="codex:session-d",
    agent_id="codex",
    source="codex",
    content={"input": "first meaningful prompt for session d", "output": "", "metadata": {"agent": "codex", "event_type": "UserPromptSubmit"}},
)
db.insert_raw_chat_log(
    tenant_id="demo",
    principal_id="demo",
    session_id="shared-session",
    user_id="codex:shared-session",
    agent_id="codex",
    source="codex",
    content={"input": "codex shared session first message", "output": "assistant reply shared 1", "metadata": {"agent": "codex"}},
)
db.insert_raw_chat_log(
    tenant_id="demo",
    principal_id="demo",
    session_id="shared-session",
    user_id="hermes:shared-session",
    agent_id="hermes",
    source="hermes",
    content={"input": "hermes shared session first message", "output": "assistant reply shared 2", "metadata": {"agent": "hermes"}},
)

headers = {"X-API-Key": "test-key"}

sock = socket.socket()
sock.bind(("127.0.0.1", 0))
port = sock.getsockname()[1]
sock.close()

config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
server = uvicorn.Server(config)
thread = threading.Thread(target=server.run, daemon=True)
thread.start()

for _ in range(50):
    try:
        with urlopen(f"http://127.0.0.1:{port}/health") as response:
            if response.status == 200:
                break
    except Exception:
        time.sleep(0.1)
else:
    raise SystemExit("server did not start")


def get_json(path: str):
    request = Request(
        f"http://127.0.0.1:{port}{path}",
        headers=headers,
        method="GET",
    )
    try:
        with urlopen(request) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        return exc.code, body


list_status, list_payload = get_json("/v1/sessions?limit=10")
assert list_status == 200, list_payload
items = list_payload["items"]
expected_preview = long_first_message[:77].rstrip() + "..."
by_session = {(item["session_id"], item["source"]): item for item in items}
assert by_session[("session-c", "codex")]["preview"] == expected_preview, items
assert by_session[("session-c", "codex")]["preview"] != long_first_message, items
assert len(by_session[("session-c", "codex")]["preview"]) < len(long_first_message), items
assert by_session[("session-c", "codex")]["record_count"] == 1, items
assert by_session[("session-d", "codex")]["preview"] == "first meaningful prompt for session d", items
assert by_session[("session-d", "codex")]["record_count"] == 2, items
assert by_session[("shared-session", "codex")]["preview"] == "codex shared session first message", items
assert by_session[("shared-session", "hermes")]["preview"] == "hermes shared session first message", items
assert by_session[("shared-session", "codex")]["source"] == "codex", items
assert by_session[("shared-session", "hermes")]["source"] == "hermes", items
assert by_session[("shared-session", "codex")] != by_session[("shared-session", "hermes")], items

records_status, records_payload = get_json("/v1/sessions?view=records&limit=10")
assert records_status == 200, records_payload
record_items = records_payload["items"]
record_by_session = {item["session_id"]: item for item in record_items}
assert record_by_session["session-b"]["input"] == "first user message for session b"
assert record_by_session["session-b"]["output"] == "assistant reply b1"

detail_status, detail = get_json("/v1/sessions/session-a")
assert detail_status == 200, detail
assert detail["session_id"] == "session-a"
assert detail["source"] == "codex"
assert detail["record_count"] == 2
assert detail["items"][0]["input"] == "first user message for session a"
assert detail["items"][1]["output"] == "assistant reply a2"
assert detail["items"][0]["metadata"]["agent"] == "codex"

collision_status, collision_payload = get_json("/v1/sessions/shared-session")
assert collision_status == 409, collision_payload
assert "pass source" in collision_payload

codex_status, codex_detail = get_json("/v1/sessions/shared-session?source=codex")
assert codex_status == 200, codex_detail
assert codex_detail["session_id"] == "shared-session"
assert codex_detail["source"] == "codex"
assert codex_detail["record_count"] == 1
assert codex_detail["items"][0]["input"] == "codex shared session first message"
assert codex_detail["items"][0]["metadata"]["agent"] == "codex"

hermes_status, hermes_detail = get_json("/v1/sessions/shared-session?source=hermes")
assert hermes_status == 200, hermes_detail
assert hermes_detail["session_id"] == "shared-session"
assert hermes_detail["source"] == "hermes"
assert hermes_detail["record_count"] == 1
assert hermes_detail["items"][0]["input"] == "hermes shared session first message"
assert hermes_detail["items"][0]["metadata"]["agent"] == "hermes"
PY
