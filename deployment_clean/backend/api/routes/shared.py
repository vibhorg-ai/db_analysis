"""
Shared state and helpers for API routes. Used by all sub-routers.
"""

from __future__ import annotations

import re
import threading
import uuid
from typing import Any
from urllib.parse import quote_plus

from backend.api.schemas import ConnectDBRequest
from backend.core.connection_manager import (
    get_active_connections_snapshot as _get_active_snapshot,
    register_connection as _register_conn,
    unregister_connection as _unregister_conn,
    resolve_connection as _resolve_connection_impl,
    iterate_connections as _iterate_connections,
)

# State (thread-safe access via connection_manager for registration)
_active_connections: dict[str, dict[str, Any]] = {}
_connections_lock = threading.Lock()

_orchestrator: Any = None
_orchestrator_lock = threading.Lock()

_llm_router: Any = None
_llm_router_lock = threading.Lock()


def get_active_connections() -> dict[str, dict[str, Any]]:
    return _active_connections


def get_connections_lock() -> threading.Lock:
    return _connections_lock


def register_conn(conn_id: str, data: dict[str, Any]) -> None:
    with _connections_lock:
        _active_connections[conn_id] = data
    _register_conn(conn_id, data)


def unregister_conn(conn_id: str) -> dict[str, Any] | None:
    with _connections_lock:
        popped = _active_connections.pop(conn_id, None)
    if popped is not None:
        _unregister_conn(conn_id)
    return popped


def sanitize_error(msg: str) -> str:
    """Strip credentials from error messages."""
    if not msg:
        return msg
    out = re.sub(
        r"(postgresql://[^:]+:)([^@]+)(@)",
        r"\1***\3",
        msg,
        flags=re.IGNORECASE,
    )
    out = re.sub(r"(?i)(password|api_key|secret|token)[=:]\s*[^\s&]+", r"\1=***", out)
    return out


def chat_reply_to_string(reply_raw: Any) -> str:
    """Ensure chat reply is a plain string."""
    if reply_raw is None:
        return ""
    if isinstance(reply_raw, str):
        return reply_raw
    if isinstance(reply_raw, dict):
        inner = reply_raw.get("message", "")
        return chat_reply_to_string(inner) if inner != "" else ""
    inner = getattr(reply_raw, "message", None)
    if inner is not None:
        return chat_reply_to_string(inner)
    return ""


def get_orchestrator():
    """Lazy singleton for AgentOrchestrator."""
    global _orchestrator
    with _orchestrator_lock:
        if _orchestrator is None:
            from backend.agents.agent_orchestrator import AgentOrchestrator
            _orchestrator = AgentOrchestrator()
        return _orchestrator


def get_llm_router():
    """Lazy singleton for LLMRouter."""
    global _llm_router
    with _llm_router_lock:
        if _llm_router is None:
            from backend.core.llm_router import LLMRouter
            _llm_router = LLMRouter()
        return _llm_router


def build_postgres_dsn(req: ConnectDBRequest) -> str:
    """Build postgresql DSN from ConnectDBRequest."""
    if req.dsn:
        return req.dsn
    host = req.host or "localhost"
    port = req.port or 5432
    database = req.database or "postgres"
    user = quote_plus(req.user or "postgres")
    password = quote_plus(req.password or "")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def resolve_connection(connection_id: str | None) -> tuple[str | None, dict[str, Any] | None]:
    """Get active connection by id. Returns (conn_id, conn_dict)."""
    with _connections_lock:
        if connection_id:
            conn = _active_connections.get(connection_id)
            return (connection_id if conn else None, conn)
        if _active_connections:
            cid, c = next(iter(_active_connections.items()))
            return (cid, c)
        return (None, None)
