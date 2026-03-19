"""
Thread-safe connection manager.

Provides a clean API for schedulers and other modules to access
active connections without reaching into routes internals.
"""

from __future__ import annotations

import threading
from typing import Any

_active_connections: dict[str, dict[str, Any]] = {}
_connections_lock = threading.Lock()


def register_connection(conn_id: str, conn_data: dict[str, Any]) -> None:
    with _connections_lock:
        _active_connections[conn_id] = conn_data


def unregister_connection(conn_id: str) -> dict[str, Any] | None:
    with _connections_lock:
        return _active_connections.pop(conn_id, None)


def get_connection(conn_id: str) -> dict[str, Any] | None:
    with _connections_lock:
        return _active_connections.get(conn_id)


def get_active_connections_snapshot() -> dict[str, dict[str, Any]]:
    """Return a shallow copy safe to iterate outside the lock."""
    with _connections_lock:
        return dict(_active_connections)


def get_all_connection_ids() -> list[str]:
    with _connections_lock:
        return list(_active_connections.keys())


def resolve_connection(connection_id: str | None) -> tuple[str | None, dict[str, Any] | None]:
    """Get active connection by id. If None, return first available."""
    with _connections_lock:
        if connection_id:
            conn = _active_connections.get(connection_id)
            return (connection_id if conn else None, conn)
        if _active_connections:
            cid, c = next(iter(_active_connections.items()))
            return (cid, c)
        return (None, None)


def iterate_connections() -> list[tuple[str, dict[str, Any]]]:
    """Return list of (conn_id, conn_data) tuples safe to iterate."""
    with _connections_lock:
        return list(_active_connections.items())
