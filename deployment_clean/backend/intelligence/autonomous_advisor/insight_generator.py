"""
Thread-safe in-memory insight store.

Insights are the final output of the Autonomous Database Advisor —
scored recommendations with category, impact, confidence, risk, and optional SQL.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Insight:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    category: str = "performance"  # performance, schema, risk, workload
    title: str = ""
    description: str = ""
    recommendation: str = ""
    suggested_sql: str | None = None
    impact: str = "medium"  # high, medium, low
    confidence: float = 0.0  # 0–100
    risk: str = "low"  # high, medium, low
    connection_id: str = ""
    source: str = "advisor"
    dismissed: bool = False
    dismissed_at: float | None = None


class InsightGenerator:
    """Produces and stores Insight objects from raw recommendation data."""

    def __init__(self) -> None:
        self._insights: list[Insight] = []
        self._lock = threading.Lock()

    def create(self, **kwargs: Any) -> Insight:
        insight = Insight(**kwargs)
        with self._lock:
            self._insights.append(insight)
        return insight

    def bulk_create(self, items: list[dict[str, Any]]) -> list[Insight]:
        created: list[Insight] = []
        with self._lock:
            for item in items:
                ins = Insight(**item)
                self._insights.append(ins)
                created.append(ins)
        return created

    def get_all(self, *, include_dismissed: bool = False) -> list[Insight]:
        with self._lock:
            if include_dismissed:
                return list(self._insights)
            return [i for i in self._insights if not i.dismissed]

    def get_by_category(self, category: str) -> list[Insight]:
        with self._lock:
            return [i for i in self._insights if i.category == category and not i.dismissed]

    def get_by_connection(self, connection_id: str) -> list[Insight]:
        with self._lock:
            return [i for i in self._insights if i.connection_id == connection_id and not i.dismissed]

    def dismiss(self, insight_id: str) -> bool:
        with self._lock:
            for i in self._insights:
                if i.id == insight_id:
                    i.dismissed = True
                    i.dismissed_at = time.time()
                    return True
        return False

    def clear_for_connection(self, connection_id: str) -> int:
        with self._lock:
            before = len(self._insights)
            self._insights = [i for i in self._insights if i.connection_id != connection_id]
            return before - len(self._insights)

    def count(self, *, include_dismissed: bool = False) -> int:
        with self._lock:
            if include_dismissed:
                return len(self._insights)
            return sum(1 for i in self._insights if not i.dismissed)


_store: InsightGenerator | None = None
_store_lock = threading.Lock()


def get_insight_store() -> InsightGenerator:
    global _store
    with _store_lock:
        if _store is None:
            _store = InsightGenerator()
        return _store
