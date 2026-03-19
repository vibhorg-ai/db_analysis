"""Tracks health/performance metrics over time."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PerformanceSnapshot:
    timestamp: float
    health_score: int
    metrics: dict[str, Any] = field(default_factory=dict)
    alerts: list[dict[str, Any]] = field(default_factory=list)


class PerformanceHistory:
    def __init__(self, max_snapshots: int = 1000) -> None:
        self._snapshots: list[PerformanceSnapshot] = []
        self._max = max_snapshots
        self._lock = threading.Lock()

    def record(
        self,
        health_score: int,
        metrics: dict[str, Any],
        alerts: list[dict[str, Any]] | None = None,
    ) -> PerformanceSnapshot:
        """Record a performance snapshot."""
        snap = PerformanceSnapshot(
            timestamp=time.time(),
            health_score=health_score,
            metrics=dict(metrics),
            alerts=list(alerts) if alerts else [],
        )
        with self._lock:
            self._snapshots.append(snap)
            if len(self._snapshots) > self._max:
                self._snapshots = self._snapshots[-self._max :]
            return snap

    def get_history(self, limit: int = 100) -> list[PerformanceSnapshot]:
        """Return most recent snapshots."""
        with self._lock:
            return list(self._snapshots[-limit:])

    def get_trend(self, hours: float = 24) -> dict[str, Any]:
        """Return performance trend: avg score, min score, alert count over last N hours."""
        cutoff = time.time() - (hours * 3600)
        with self._lock:
            recent = [s for s in self._snapshots if s.timestamp >= cutoff]
        if not recent:
            return {
                "avg_score": 0,
                "min_score": 0,
                "max_score": 0,
                "alert_count": 0,
                "snapshot_count": 0,
            }
        scores = [s.health_score for s in recent]
        alerts = sum(len(s.alerts) for s in recent)
        return {
            "avg_score": sum(scores) / len(scores),
            "min_score": min(scores),
            "max_score": max(scores),
            "alert_count": alerts,
            "snapshot_count": len(recent),
        }

    def get_since(self, since_timestamp: float) -> list[PerformanceSnapshot]:
        """Return snapshots since the given timestamp."""
        with self._lock:
            return [s for s in self._snapshots if s.timestamp > since_timestamp]


_instance: PerformanceHistory | None = None
_init_lock = threading.Lock()


def get_performance_history() -> PerformanceHistory:
    """Return singleton PerformanceHistory instance."""
    global _instance
    if _instance is None:
        with _init_lock:
            if _instance is None:
                _instance = PerformanceHistory()
    return _instance
