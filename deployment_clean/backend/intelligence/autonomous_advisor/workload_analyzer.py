"""
Workload analyzer for the Autonomous Database Advisor.

Analyzes query history and performance data to detect patterns:
- Frequently executed queries
- Slow queries / sequential scans
- Peak traffic periods
- Hot tables and contention
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from backend.time_travel.query_history import get_query_history
from backend.time_travel.performance_history import get_performance_history

logger = logging.getLogger(__name__)


class WorkloadAnalyzer:
    """Stateless analyzer — reads from time-travel stores each run."""

    def analyze(self) -> dict[str, Any]:
        """Return workload analysis: frequent queries, slow queries, hot tables, trends."""
        qh = get_query_history()
        ph = get_performance_history()

        history = qh.get_history(limit=5000)
        slow = qh.get_slow_queries(threshold_ms=1000, limit=50)
        trend = ph.get_trend(hours=24)

        frequent = self._find_frequent_queries(history)
        hot_tables = self._find_hot_tables(history)
        slow_patterns = self._find_slow_patterns(slow)
        perf_trend = self._summarize_trend(trend)

        return {
            "frequent_queries": frequent,
            "slow_patterns": slow_patterns,
            "hot_tables": hot_tables,
            "performance_trend": perf_trend,
            "total_queries_analyzed": len(history),
            "slow_query_count": len(slow),
        }

    def _find_frequent_queries(self, history: list) -> list[dict[str, Any]]:
        normalized: Counter[str] = Counter()
        durations: dict[str, list[float]] = {}

        for record in history:
            sql = getattr(record, "query", "").strip()
            if not sql:
                continue
            key = self._normalize_query(sql)
            normalized[key] += 1
            dur = getattr(record, "duration_ms", None)
            if dur is not None:
                durations.setdefault(key, []).append(dur)

        results: list[dict[str, Any]] = []
        for query, count in normalized.most_common(20):
            if count < 5:
                break
            durs = durations.get(query, [])
            avg_ms = sum(durs) / len(durs) if durs else 0
            results.append({
                "query_pattern": query[:200],
                "execution_count": count,
                "avg_duration_ms": round(avg_ms, 1),
                "total_time_ms": round(sum(durs), 1),
            })
        return results

    def _find_slow_patterns(self, slow_queries: list) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for record in slow_queries:
            sql = getattr(record, "query", "").strip()
            key = self._normalize_query(sql)
            if key in seen:
                continue
            seen.add(key)
            dur = getattr(record, "duration_ms", 0) or 0
            results.append({
                "query_pattern": sql[:300],
                "duration_ms": dur,
                "source": getattr(record, "source", ""),
            })
            if len(results) >= 15:
                break
        return results

    def _find_hot_tables(self, history: list) -> list[dict[str, Any]]:
        table_refs: Counter[str] = Counter()
        for record in history:
            sql = getattr(record, "query", "").upper()
            for token in sql.split():
                if "." in token:
                    cleaned = token.strip("();,\"'`")
                    if cleaned and not cleaned.startswith("PG_"):
                        table_refs[cleaned.lower()] += 1

        return [
            {"table": table, "reference_count": count}
            for table, count in table_refs.most_common(10)
            if count >= 3
        ]

    def _summarize_trend(self, trend: list) -> dict[str, Any]:
        if not trend:
            return {"data_points": 0}
        scores = [getattr(s, "health_score", 0) for s in trend]
        return {
            "data_points": len(trend),
            "avg_health_score": round(sum(scores) / len(scores), 1) if scores else 0,
            "min_health_score": min(scores) if scores else 0,
            "max_health_score": max(scores) if scores else 0,
        }

    @staticmethod
    def _normalize_query(sql: str) -> str:
        import re
        normalized = re.sub(r"'[^']*'", "'?'", sql)
        normalized = re.sub(r"\b\d+\b", "?", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized[:200]
