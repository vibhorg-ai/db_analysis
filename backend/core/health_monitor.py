"""
Health metrics collection for the monitoring agent.

Collects health metrics from PostgreSQL and Couchbase connectors,
and computes a weighted health score (0-100) for PostgreSQL.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _scalar(rows: list[dict[str, Any]], key: str | None = None) -> int | float | None:
    """Extract scalar value from first row. Uses first column if key is None."""
    if not rows:
        return None
    row = rows[0]
    if key:
        return row.get(key)
    return list(row.values())[0] if row else None


class HealthMonitor:
    """Collects health metrics from connected databases."""

    async def collect_postgres_metrics(self, connector: Any) -> dict[str, Any]:
        """
        Collect metrics from PostgreSQL: connections, cache hit ratio,
        dead tuples, long queries, locks.
        Uses connector.execute_read_only() for each metric query.
        """
        metrics: dict[str, Any] = {
            "connection_status": "unknown",
            "active_connections": None,
            "max_connections": None,
            "cache_hit_ratio": None,
            "dead_tuples_ratio": None,
            "long_running_queries": None,
            "locks_waiting": None,
            "error": None,
        }

        # Check basic connectivity
        try:
            health = await connector.health_check()
            metrics["connection_status"] = "ok" if health.get("connected") else "error"
            if not health.get("connected"):
                metrics["error"] = health.get("error", "Not connected")
                return metrics
        except Exception as e:
            metrics["connection_status"] = "error"
            metrics["error"] = str(e)
            return metrics

        # 1. Active connections vs max
        try:
            rows = await connector.execute_read_only(
                "SELECT count(*) AS cnt FROM pg_stat_activity WHERE state = 'active'",
                timeout=10.0,
            )
            metrics["active_connections"] = _scalar(rows, "cnt")
        except Exception as e:
            logger.debug("Active connections query failed: %s", e)

        try:
            rows = await connector.execute_read_only(
                "SELECT setting::int AS val FROM pg_settings WHERE name = 'max_connections'",
                timeout=10.0,
            )
            metrics["max_connections"] = _scalar(rows, "val")
        except Exception as e:
            logger.debug("Max connections query failed: %s", e)

        # 2. Cache hit ratio
        try:
            rows = await connector.execute_read_only("""
                SELECT COALESCE(
                    sum(heap_blks_hit)::float / NULLIF(sum(heap_blks_hit) + sum(heap_blks_read), 0),
                    1.0
                ) AS ratio FROM pg_statio_user_tables
            """, timeout=10.0)
            metrics["cache_hit_ratio"] = _scalar(rows, "ratio")
        except Exception as e:
            logger.debug("Cache hit ratio query failed: %s", e)

        # 3. Dead tuples ratio
        try:
            rows = await connector.execute_read_only("""
                SELECT COALESCE(
                    sum(n_dead_tup)::float / NULLIF(sum(n_live_tup) + sum(n_dead_tup), 0),
                    0.0
                ) AS ratio FROM pg_stat_user_tables
            """, timeout=10.0)
            metrics["dead_tuples_ratio"] = _scalar(rows, "ratio")
        except Exception as e:
            logger.debug("Dead tuples ratio query failed: %s", e)

        # 4. Long-running queries (>30s)
        try:
            rows = await connector.execute_read_only("""
                SELECT count(*) AS cnt FROM pg_stat_activity
                WHERE state = 'active' AND now() - query_start > interval '30 seconds'
            """, timeout=10.0)
            metrics["long_running_queries"] = _scalar(rows, "cnt")
        except Exception as e:
            logger.debug("Long-running queries query failed: %s", e)

        # 5. Locks (not granted)
        try:
            rows = await connector.execute_read_only(
                "SELECT count(*) AS cnt FROM pg_locks WHERE NOT granted",
                timeout=10.0,
            )
            metrics["locks_waiting"] = _scalar(rows, "cnt")
        except Exception as e:
            logger.debug("Locks query failed: %s", e)

        return metrics

    async def collect_couchbase_metrics(self, connector: Any) -> dict[str, Any]:
        """
        Collect metrics from Couchbase: connection status, bucket accessibility.
        Uses connector.health_check() and connector.fetch_bucket_info().
        """
        metrics: dict[str, Any] = {
            "connection_status": "unknown",
            "accessible": False,
            "bucket": None,
            "item_count": None,
            "error": None,
        }
        try:
            health = await connector.health_check()
            metrics["connection_status"] = "ok" if health.get("connected") else "error"
            metrics["accessible"] = health.get("accessible", False)
            metrics["bucket"] = health.get("bucket")
            if not health.get("connected"):
                metrics["error"] = health.get("error", "Not connected")
                return metrics
        except Exception as e:
            metrics["connection_status"] = "error"
            metrics["error"] = str(e)
            return metrics

        try:
            bucket_info = await connector.fetch_bucket_info()
            metrics["bucket"] = bucket_info.get("bucket_name") or metrics["bucket"]
            metrics["item_count"] = bucket_info.get("item_count")
        except Exception as e:
            logger.debug("Couchbase bucket info failed: %s", e)

        return metrics

    def compute_health_score(self, metrics: dict[str, Any]) -> dict[str, Any]:
        """
        Compute weighted health score (0-100) from PostgreSQL-style metrics.
        Weights: connection_status=30, active_connections=15, cache_hit=15,
        dead_tuples=10, long_queries=15, locks=15.
        Returns: {score, status (healthy/warning/critical), metrics, alerts}
        """
        alerts: list[str] = []
        score = 0.0

        # connection_status (30 pts)
        conn = metrics.get("connection_status")
        if conn == "ok":
            score += 30
        else:
            score += 0
            alerts.append("Database connection unhealthy or error")

        # active_connections (15 pts) - penalize if near max
        active = metrics.get("active_connections")
        max_conn = metrics.get("max_connections")
        if active is not None and max_conn is not None and max_conn > 0:
            usage = active / max_conn
            if usage >= 0.9:
                score += 0
                alerts.append("Connection pool near saturation (>90%)")
            elif usage >= 0.7:
                score += 5
                alerts.append("Connection pool under pressure (>70%)")
            else:
                score += 15
        elif active is not None:
            score += 15

        # cache_hit (15 pts) - expect > 0.99 for good health
        hit = metrics.get("cache_hit_ratio")
        if hit is not None:
            if hit >= 0.99:
                score += 15
            elif hit >= 0.95:
                score += 10
                alerts.append("Cache hit ratio below 99%")
            elif hit >= 0.9:
                score += 5
                alerts.append("Cache hit ratio below 95%")
            else:
                score += 0
                alerts.append("Cache hit ratio critically low (<90%)")
        else:
            score += 15  # no data = assume ok

        # dead_tuples (10 pts) - low ratio is good
        dead = metrics.get("dead_tuples_ratio")
        if dead is not None:
            if dead <= 0.05:
                score += 10
            elif dead <= 0.1:
                score += 5
                alerts.append("Dead tuple ratio elevated; consider VACUUM")
            else:
                score += 0
                alerts.append("Dead tuple ratio high; VACUUM recommended")
        else:
            score += 10

        # long_queries (15 pts)
        long_q = metrics.get("long_running_queries")
        if long_q is not None:
            if long_q == 0:
                score += 15
            elif long_q <= 2:
                score += 10
                alerts.append("Long-running queries detected (>30s)")
            else:
                score += 0
                alerts.append(f"{long_q} long-running queries (>30s)")
        else:
            score += 15

        # locks (15 pts)
        locks = metrics.get("locks_waiting")
        if locks is not None:
            if locks == 0:
                score += 15
            elif locks <= 5:
                score += 8
                alerts.append("Lock contention detected")
            else:
                score += 0
                alerts.append(f"{locks} waiting locks; contention critical")
        else:
            score += 15

        # Couchbase-only metrics: simple pass/fail
        if "accessible" in metrics and "cache_hit_ratio" not in metrics:
            score = 100.0 if metrics.get("accessible") else 0.0
            if not metrics.get("accessible"):
                alerts.append("Couchbase bucket not accessible")

        status = "healthy" if score >= 80 else ("warning" if score >= 50 else "critical")

        return {
            "score": round(min(100, max(0, score)), 1),
            "status": status,
            "metrics": metrics,
            "alerts": alerts,
        }
