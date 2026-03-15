"""
Thread-safe schema metadata cache per DSN with configurable TTL.
Uses SHA-256 hash of DSN as cache key (avoids storing raw DSN).
"""

from __future__ import annotations

import hashlib
import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

from backend.core.config import get_settings


def _dsn_key(dsn: str) -> str:
    """Return SHA-256 hash of DSN as cache key."""
    return hashlib.sha256(dsn.encode("utf-8")).hexdigest()


class SchemaCache:
    """Thread-safe schema cache with TTL per DSN."""

    def __init__(self) -> None:
        self._cache: dict[str, tuple[list[dict], float]] = {}
        self._lock = threading.Lock()

    def get(self, dsn: str) -> list[dict] | None:
        """
        Return cached tables list for DSN, or None if expired/missing.
        If TTL is 0, always returns None (caching disabled).
        """
        settings = get_settings()
        if settings.schema_cache_ttl_seconds <= 0:
            return None

        key = _dsn_key(dsn)
        now = time.monotonic()

        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            tables, stored_at = entry
            if now - stored_at >= settings.schema_cache_ttl_seconds:
                del self._cache[key]
                return None
            return tables

    def set(self, dsn: str, tables: Sequence[dict]) -> None:
        """Store tables list with current timestamp. No-op if TTL is 0."""
        settings = get_settings()
        if settings.schema_cache_ttl_seconds <= 0:
            return

        key = _dsn_key(dsn)
        with self._lock:
            self._cache[key] = (list(tables), time.monotonic())

    def invalidate(self, dsn: str) -> None:
        """Remove cache entry for DSN."""
        key = _dsn_key(dsn)
        with self._lock:
            self._cache.pop(key, None)

    def invalidate_all(self) -> None:
        """Clear entire cache."""
        with self._lock:
            self._cache.clear()


_cache_instance: SchemaCache | None = None
_cache_lock = threading.Lock()


def get_schema_cache() -> SchemaCache:
    """Module-level singleton for SchemaCache."""
    global _cache_instance
    with _cache_lock:
        if _cache_instance is None:
            _cache_instance = SchemaCache()
        return _cache_instance
