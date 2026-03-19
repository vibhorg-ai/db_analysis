"""Tracks query execution history for time-travel analysis."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class QueryRecord:
    timestamp: float
    query: str
    duration_ms: float | None = None
    source: str = ""  # which agent/endpoint triggered it


class QueryHistory:
    def __init__(self, max_records: int = 10000) -> None:
        self._records: list[QueryRecord] = []
        self._max = max_records
        self._lock = threading.Lock()

    def record(
        self,
        query: str,
        duration_ms: float | None = None,
        source: str = "",
    ) -> None:
        """Record a query execution."""
        rec = QueryRecord(
            timestamp=time.time(),
            query=query,
            duration_ms=duration_ms,
            source=source,
        )
        with self._lock:
            self._records.append(rec)
            if len(self._records) > self._max:
                self._records = self._records[-self._max :]

    def get_history(self, limit: int = 100) -> list[QueryRecord]:
        """Return most recent records."""
        with self._lock:
            return list(self._records[-limit:])

    def get_slow_queries(
        self,
        threshold_ms: float = 1000,
        limit: int = 50,
    ) -> list[QueryRecord]:
        """Return slow queries (duration >= threshold_ms)."""
        with self._lock:
            slow = [r for r in self._records if r.duration_ms is not None and r.duration_ms >= threshold_ms]
            return list(slow[-limit:])

    def get_queries_since(self, since_timestamp: float) -> list[QueryRecord]:
        """Return queries executed since the given timestamp."""
        with self._lock:
            return [r for r in self._records if r.timestamp > since_timestamp]


_instance: QueryHistory | None = None
_init_lock = threading.Lock()


def get_query_history() -> QueryHistory:
    """Return singleton QueryHistory instance."""
    global _instance
    if _instance is None:
        with _init_lock:
            if _instance is None:
                _instance = QueryHistory()
    return _instance
