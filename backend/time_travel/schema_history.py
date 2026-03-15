"""Tracks schema snapshots over time."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SchemaSnapshot:
    timestamp: float
    checksum: str  # SHA-256 of schema metadata
    tables: list[dict[str, Any]]
    changes: list[str] = field(default_factory=list)  # change descriptions vs previous


class SchemaHistory:
    """Append-only schema history store."""

    def __init__(self) -> None:
        self._snapshots: list[SchemaSnapshot] = []
        self._lock = threading.Lock()

    def _compute_checksum(self, schema_metadata: list[dict]) -> str:
        """Compute SHA-256 checksum of normalized schema metadata."""
        normalized = json.dumps(schema_metadata, sort_keys=True, default=str)
        return hashlib.sha256(normalized.encode()).hexdigest()

    def _detect_changes(
        self, prev_tables: list[dict], curr_tables: list[dict]
    ) -> list[str]:
        """Detect added/removed tables and columns vs previous snapshot."""
        changes: list[str] = []
        prev_map: dict[str, dict] = {t.get("name", t.get("table_name", str(i))): t for i, t in enumerate(prev_tables)}
        curr_map: dict[str, dict] = {t.get("name", t.get("table_name", str(i))): t for i, t in enumerate(curr_tables)}

        prev_names = set(prev_map.keys())
        curr_names = set(curr_map.keys())

        added = curr_names - prev_names
        removed = prev_names - curr_names
        for name in added:
            changes.append(f"Table added: {name}")
        for name in removed:
            changes.append(f"Table removed: {name}")

        for name in prev_names & curr_names:
            prev_cols = {c.get("name", c.get("column_name", str(j))) for j, c in enumerate(prev_map[name].get("columns", []))}
            curr_cols = {c.get("name", c.get("column_name", str(j))) for j, c in enumerate(curr_map[name].get("columns", []))}
            col_added = curr_cols - prev_cols
            col_removed = prev_cols - curr_cols
            if col_added:
                changes.append(f"Table {name}: columns added: {', '.join(col_added)}")
            if col_removed:
                changes.append(f"Table {name}: columns removed: {', '.join(col_removed)}")

        return changes

    def record(self, schema_metadata: list[dict]) -> SchemaSnapshot:
        """Record a schema snapshot. Detect changes vs previous snapshot."""
        checksum = self._compute_checksum(schema_metadata)
        tables = list(schema_metadata)

        with self._lock:
            changes: list[str] = []
            if self._snapshots:
                prev = self._snapshots[-1]
                changes = self._detect_changes(prev.tables, tables)
            snapshot = SchemaSnapshot(
                timestamp=time.time(),
                checksum=checksum,
                tables=tables,
                changes=changes,
            )
            self._snapshots.append(snapshot)
            return snapshot

    def get_history(self, limit: int = 50) -> list[SchemaSnapshot]:
        """Return most recent snapshots."""
        with self._lock:
            return list(self._snapshots[-limit:])

    def get_changes_since(self, since_timestamp: float) -> list[dict]:
        """Return changes since a given timestamp."""
        with self._lock:
            out: list[dict] = []
            for s in self._snapshots:
                if s.timestamp > since_timestamp and s.changes:
                    out.append({
                        "timestamp": s.timestamp,
                        "changes": s.changes,
                        "checksum": s.checksum,
                    })
            return out

    def find_when_table_changed(self, table_name: str) -> list[dict]:
        """Find snapshots where a given table was added/removed/modified."""
        with self._lock:
            out: list[dict] = []
            for s in self._snapshots:
                relevant = [c for c in s.changes if table_name in c.lower()]
                if relevant:
                    out.append({
                        "timestamp": s.timestamp,
                        "changes": relevant,
                        "checksum": s.checksum,
                    })
            return out

    def find_when_column_changed(self, table_name: str, column_name: str) -> list[dict]:
        """Find snapshots where a given column was added/removed."""
        with self._lock:
            out: list[dict] = []
            for s in self._snapshots:
                relevant = [
                    c for c in s.changes
                    if (table_name.lower() in c.lower() and column_name.lower() in c.lower())
                ]
                if relevant:
                    out.append({
                        "timestamp": s.timestamp,
                        "changes": relevant,
                        "checksum": s.checksum,
                    })
            return out


_instance: SchemaHistory | None = None


def get_schema_history() -> SchemaHistory:
    """Return singleton SchemaHistory instance."""
    global _instance
    if _instance is None:
        _instance = SchemaHistory()
    return _instance
