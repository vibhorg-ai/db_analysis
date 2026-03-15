"""
Sync app connections to MCP config format.
Provides MCP-compatible postgres and couchbase config from settings or synced connections.
"""

from __future__ import annotations

import re
import threading
from typing import Any

from backend.core.config import get_settings

_synced_postgres: dict[str, Any] | None = None
_synced_couchbase: dict[str, Any] | None = None
_sync_lock = threading.Lock()


def _mask_dsn(dsn: str) -> str:
    """Strip password from postgresql DSN for safe logging."""
    if not dsn:
        return ""
    # Match password in postgresql://user:password@host:port/db
    pattern = re.compile(
        r"(postgresql://[^:]+:)([^@]+)(@.*)",
        re.IGNORECASE,
    )
    return pattern.sub(r"\1***\3", dsn)


def get_mcp_postgres_config() -> dict[str, Any]:
    """Return dict with dsn and configured flag. Uses synced value or settings fallback."""
    with _sync_lock:
        if _synced_postgres is not None:
            return _synced_postgres.copy()

    settings = get_settings()
    dsn = settings.mcp_postgres_dsn
    return {
        "dsn": dsn,
        "configured": bool(dsn),
    }


def get_mcp_couchbase_config() -> dict[str, Any]:
    """Return dict with connection_string, bucket, username, password, configured flag."""
    with _sync_lock:
        if _synced_couchbase is not None:
            return _synced_couchbase.copy()

    settings = get_settings()
    return {
        "connection_string": settings.mcp_couchbase_connection_string,
        "bucket": settings.mcp_couchbase_bucket,
        "username": settings.mcp_couchbase_username,
        "password": settings.mcp_couchbase_password,
        "configured": bool(
            settings.mcp_couchbase_connection_string
            and settings.mcp_couchbase_bucket
        ),
    }


def sync_connections_to_mcp(connections: list[dict[str, Any]]) -> None:
    """
    Take list of connection dicts, find first postgres and first couchbase,
    build MCP config from them and store as synced state.
    """
    global _synced_postgres, _synced_couchbase

    postgres_conn: dict[str, Any] | None = None
    couchbase_conn: dict[str, Any] | None = None

    for c in connections:
        engine = (c.get("engine") or "").lower()
        if engine == "postgres" and postgres_conn is None:
            postgres_conn = c
        elif engine == "couchbase" and couchbase_conn is None:
            couchbase_conn = c
        if postgres_conn and couchbase_conn:
            break

    with _sync_lock:
        if postgres_conn is not None:
            _synced_postgres = {
                "dsn": postgres_conn.get("dsn") or _build_postgres_dsn(postgres_conn),
                "configured": True,
            }
        else:
            _synced_postgres = None

        if couchbase_conn is not None:
            _synced_couchbase = {
                "connection_string": couchbase_conn.get("connection_string", ""),
                "bucket": couchbase_conn.get("bucket", ""),
                "username": couchbase_conn.get("username", ""),
                "password": couchbase_conn.get("password", ""),
                "configured": True,
            }
        else:
            _synced_couchbase = None


def _build_postgres_dsn(conn: dict[str, Any]) -> str:
    """Build postgresql DSN from connection dict."""
    from urllib.parse import quote_plus

    host = conn.get("host") or "localhost"
    port = conn.get("port") or 5432
    database = conn.get("database") or ""
    user = quote_plus(conn.get("user") or "")
    password = quote_plus(conn.get("password") or "")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def get_mcp_status() -> dict[str, Any]:
    """Return dict with postgres and couchbase configured status."""
    pg = get_mcp_postgres_config()
    cb = get_mcp_couchbase_config()
    return {
        "postgres": {"configured": pg["configured"]},
        "couchbase": {"configured": cb["configured"]},
    }
