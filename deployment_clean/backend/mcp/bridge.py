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


def get_mcp_status() -> dict[str, Any]:
    """Return dict with postgres and couchbase configured status."""
    pg = get_mcp_postgres_config()
    cb = get_mcp_couchbase_config()
    return {
        "postgres": {"configured": pg["configured"]},
        "couchbase": {"configured": cb["configured"]},
    }
