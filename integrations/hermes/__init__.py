"""Capitok archive companion plugin for Hermes Agent.

Auto-saves every conversation turn to Capitok via HTTP hooks.

Config via environment or $HERMES_HOME/config.yaml:
  CAPITOK_API_URL  - Capitok endpoint (default: http://localhost:8000)
  CAPITOK_API_KEY  - API key for authentication (required)

Or in config.yaml:
  plugins:
    capitok:
      enabled: true
      api_url: http://localhost:8000
      api_key: dev-ingest-search-key
      auto_save: true
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class CapitokClient:
    """HTTP client for the Capitok archive gateway."""

    def __init__(self, api_url: str, api_key: str, timeout: float = 5.0):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._session_id = None
        self._user_id = None

    def set_ids(self, session_id: str, user_id: str) -> None:
        """Set session and user identifiers for this client."""
        self._session_id = session_id
        self._user_id = user_id

    def ingest(
        self,
        user_input: str,
        assistant_output: str,
        source: str = "hermes",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """POST to /v1/ingest with turn data."""
        if not self._session_id or not self._user_id:
            raise ValueError("session_id and user_id must be set before ingest")

        payload = {
            "session_id": self._session_id,
            "user_id": self._user_id,
            "source": source,
            "input": user_input,
            "output": assistant_output,
            "metadata": metadata or {},
        }

        url = f"{self.api_url}/v1/ingest"
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
        }
        data = json.dumps(payload).encode("utf-8")

        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return {"status": "success", "result": result}
        except urllib.error.HTTPError as e:
            error_msg = e.read().decode("utf-8", errors="ignore")
            return {"status": "error", "code": e.code, "message": error_msg}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def search(self, query: str, top_k: int = 10) -> Dict[str, Any]:
        """GET /v1/search to retrieve derived recall records."""
        if not self._user_id:
            raise ValueError("user_id must be set before search")

        url = f"{self.api_url}/v1/search?query={urllib.parse.quote(query)}&top_k={top_k}"
        headers = {"X-API-Key": self.api_key}

        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return {"status": "success", "result": result}
        except urllib.error.HTTPError as e:
            error_msg = e.read().decode("utf-8", errors="ignore")
            return {"status": "error", "code": e.code, "message": error_msg}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def health(self) -> bool:
        """Check if Capitok is reachable."""
        try:
            url = f"{self.api_url}/health"
            with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                return resp.status == 200
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Plugin state
# ---------------------------------------------------------------------------

_client: Optional[CapitokClient] = None
_config: Dict[str, Any] = {}
_enabled = False
TOOLSET_NAME = "plugin_capitok"


def _load_config() -> Dict[str, Any]:
    """Load plugin config from env + hermes config.yaml."""
    config = {}

    # Environment variables take precedence
    api_url = os.environ.get("CAPITOK_API_URL", "http://localhost:8000")
    api_key = os.environ.get("CAPITOK_API_KEY", "")

    config["api_url"] = api_url
    config["api_key"] = api_key
    config["auto_save"] = os.environ.get("CAPITOK_AUTO_SAVE", "true").lower() == "true"
    config["timeout"] = float(os.environ.get("CAPITOK_TIMEOUT", "5.0"))

    # Try to load from hermes config.yaml
    try:
        from hermes_cli.config import load_config
        hermes_config = load_config()
        plugin_cfg = hermes_config.get("plugins", {}).get("capitok", {})
        if plugin_cfg:
            config.update(plugin_cfg)
    except Exception:
        pass

    return config


# ---------------------------------------------------------------------------
# Hook handlers
# ---------------------------------------------------------------------------

def _resolve_user_id(session_id: str, **kwargs) -> str:
    """Return the best available user identifier for Capitok scoping."""
    user_id = kwargs.get("user_id")
    if user_id:
        return str(user_id)
    platform = str(kwargs.get("platform") or "cli")
    return f"{platform}:{session_id}"


def on_post_llm_call(
    session_id: str,
    user_message: str,
    assistant_response: str,
    **kwargs,
) -> None:
    """Called after each successful turn completes. Auto-save to Capitok if enabled."""
    global _client, _config, _enabled

    if not _enabled or not _client:
        return

    if not _config.get("auto_save", True):
        return

    user_id = _resolve_user_id(session_id, **kwargs)

    # Set client IDs
    _client.set_ids(session_id, user_id)

    # Prepare metadata
    metadata = {
        "agent": "hermes",
        "timestamp": time.time(),
        "platform": kwargs.get("platform", ""),
        "model": kwargs.get("model", ""),
    }

    try:
        result = _client.ingest(
            user_input=user_message,
            assistant_output=assistant_response,
            metadata=metadata,
        )
        if result["status"] == "success":
            logger.debug("Capitok ingest succeeded for session %s", session_id)
        else:
            logger.warning(
                f"Capitok ingest failed: {result.get('message', 'unknown error')}"
            )
    except Exception as e:
        logger.error(f"Capitok ingest error: {e}")


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

CAPITOK_RECALL_SCHEMA = {
    "name": "capitok_recall",
    "description": "Search Capitok archive-derived recall records for past conversations and context.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query (e.g., 'meetings with Alice', 'project status')",
            },
            "top_k": {
                "type": "integer",
                "description": "Number of results to return (default: 5)",
                "default": 5,
            },
        },
        "required": ["query"],
    },
}

CAPITOK_SAVE_SCHEMA = {
    "name": "capitok_save",
    "description": "Manually save the current turn to Capitok memory.",
    "parameters": {
        "type": "object",
        "properties": {
            "note": {
                "type": "string",
                "description": "Optional note or context about what to save",
            },
        },
    },
}


# ---------------------------------------------------------------------------
# Tool handler
# ---------------------------------------------------------------------------

def _prepare_client_context(**kwargs) -> Optional[str]:
    """Populate the Capitok client with session/user context from Hermes."""
    global _client, _config

    if not _client:
        return json.dumps({"error": "Capitok client not initialized"})

    # Extract IDs from kwargs
    session_id = str(kwargs.get("session_id") or "unknown")
    user_id = _resolve_user_id(session_id, **kwargs)
    _client.set_ids(session_id, user_id)
    return None


def handle_recall_tool(args: dict, **kwargs) -> str:
    """Handle capitok_recall invocations from Hermes."""
    context_error = _prepare_client_context(**kwargs)
    if context_error:
        return context_error

    query = args.get("query", "")
    top_k = int(args.get("top_k", 5))

    if not query:
        return json.dumps({"error": "query is required"})

    result = _client.search(query, top_k=top_k)
    if result["status"] == "success":
        items = result["result"].get("items", [])
        if items:
            recalled = "\n\n".join(
                [
                    f"[{item['created_at']}] {item['text']}\n  score: {item['score']:.2f}"
                    for item in items
                ]
            )
            return json.dumps({"status": "success", "memories": recalled})
        else:
            return json.dumps({"status": "success", "memories": "No memories found."})
    else:
        return json.dumps(
            {"error": f"Search failed: {result.get('message', 'unknown')}"}
        )


def handle_save_tool(args: dict, **kwargs) -> str:
    """Handle capitok_save invocations from Hermes."""
    context_error = _prepare_client_context(**kwargs)
    if context_error:
        return context_error

    note = args.get("note", "")
    user_msg = kwargs.get("user_message", "")
    assistant_msg = kwargs.get("assistant_response", "")

    metadata = {"agent": "hermes", "manual_save": True, "note": note}

    result = _client.ingest(user_msg, assistant_msg, metadata=metadata)
    if result["status"] == "success":
        return json.dumps({"status": "success", "message": "Turn saved to Capitok."})
    else:
        return json.dumps(
            {"error": f"Save failed: {result.get('message', 'unknown')}"}
        )


# ---------------------------------------------------------------------------
# Plugin registration
# ---------------------------------------------------------------------------

def register(ctx) -> None:
    """Register Capitok plugin with Hermes."""
    global _client, _config, _enabled

    _config = _load_config()
    api_url = _config.get("api_url", "http://localhost:8000")
    api_key = _config.get("api_key", "")

    if not api_key:
        logger.warning(
            "Capitok plugin: CAPITOK_API_KEY not set. Plugin will not be active."
        )
        _enabled = False
        return

    # Initialize client
    _client = CapitokClient(api_url, api_key, timeout=_config.get("timeout", 5.0))

    # Check health
    if not _client.health():
        logger.warning(
            f"Capitok plugin: Capitok endpoint {api_url} is not reachable. "
            "Plugin registered but may not work."
        )

    _enabled = True

    # Register hook
    ctx.register_hook("post_llm_call", on_post_llm_call)

    # Register tools
    ctx.register_tool(
        name=CAPITOK_RECALL_SCHEMA["name"],
        toolset=TOOLSET_NAME,
        schema=CAPITOK_RECALL_SCHEMA,
        handler=handle_recall_tool,
    )
    ctx.register_tool(
        name=CAPITOK_SAVE_SCHEMA["name"],
        toolset=TOOLSET_NAME,
        schema=CAPITOK_SAVE_SCHEMA,
        handler=handle_save_tool,
    )

    logger.info(
        f"Capitok plugin registered (auto_save={_config.get('auto_save', True)}, "
        f"endpoint={api_url})"
    )


def get_config_schema():
    """Return config schema for Hermes setup wizard."""
    return [
        {
            "key": "api_url",
            "description": "Capitok API endpoint",
            "default": "http://localhost:8000",
            "env_var": "CAPITOK_API_URL",
        },
        {
            "key": "api_key",
            "description": "Capitok API key",
            "secret": True,
            "required": True,
            "env_var": "CAPITOK_API_KEY",
        },
        {
            "key": "auto_save",
            "description": "Auto-save turns to Capitok",
            "default": "true",
            "choices": ["true", "false"],
        },
        {
            "key": "timeout",
            "description": "HTTP request timeout (seconds)",
            "default": "5.0",
        },
    ]
