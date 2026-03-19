"""
Main Autonomous Database Advisor engine.

Coordinates workload analysis, recommendation generation, and insight storage.
Runs on a schedule (default 15 minutes) and integrates with:
- Health Monitor
- Knowledge Graph
- Dependency Engine
- Time Travel stores
- Schema metadata from active connections
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from backend.core.health_monitor import HealthMonitor
from backend.graph.knowledge_graph import get_knowledge_graph
from backend.graph.dependency_engine import get_dependency_engine
from backend.time_travel.performance_history import get_performance_history

from .workload_analyzer import WorkloadAnalyzer
from .recommendation_engine import RecommendationEngine, Recommendation
from .insight_generator import InsightGenerator, get_insight_store

logger = logging.getLogger(__name__)


class AdvisorEngine:
    """
    Orchestrates a full advisory cycle:
    1. Collect schema, health, workload, and dependency data
    2. Generate scored recommendations
    3. Store as insights
    """

    def __init__(self) -> None:
        self._workload_analyzer = WorkloadAnalyzer()
        self._rec_engine = RecommendationEngine()

    async def run_cycle(
        self,
        active_connections: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Run a full advisory cycle across all active connections.
        Returns list of insight dicts created this cycle.
        """
        all_insights: list[dict[str, Any]] = []
        store = get_insight_store()

        for conn_id, conn in active_connections.items():
            try:
                insights = await self._analyze_connection(conn_id, conn)
                all_insights.extend(insights)
            except Exception as e:
                logger.warning("Advisor failed for connection %s: %s", conn_id, e)

        return all_insights

    async def _analyze_connection(
        self, conn_id: str, conn: dict[str, Any]
    ) -> list[dict[str, Any]]:
        engine = conn.get("engine", "")
        connector = conn.get("connector")
        if not connector:
            return []

        store = get_insight_store()
        store.clear_for_connection(conn_id)

        schema: list[dict[str, Any]] = []
        health: dict[str, Any] = {}
        index_stats: list[dict[str, Any]] = []

        if engine == "postgres":
            try:
                schema = await connector.fetch_schema_metadata()
            except Exception as e:
                logger.debug("Advisor: schema fetch failed: %s", e)

            try:
                monitor = HealthMonitor()
                raw_metrics = await monitor.collect_postgres_metrics(connector)
                health = monitor.compute_health_score(raw_metrics)
            except Exception as e:
                logger.debug("Advisor: health fetch failed: %s", e)

            try:
                index_stats = await self._fetch_index_stats(connector)
            except Exception as e:
                logger.debug("Advisor: index stats failed: %s", e)

        elif engine == "couchbase":
            try:
                monitor = HealthMonitor()
                raw_metrics = await monitor.collect_couchbase_metrics(connector)
                health = monitor.compute_health_score(raw_metrics)
            except Exception as e:
                logger.debug("Advisor: couchbase health failed: %s", e)

        workload = self._workload_analyzer.analyze()

        dep_engine = get_dependency_engine()
        dependencies = dep_engine.to_dict()

        recommendations = self._rec_engine.generate(
            schema=schema or None,
            health=health or None,
            workload=workload or None,
            dependencies=dependencies or None,
            index_stats=index_stats or None,
        )

        insight_dicts: list[dict[str, Any]] = []
        for rec in recommendations:
            item = {
                "category": rec.category,
                "title": rec.title,
                "description": rec.description,
                "recommendation": rec.recommendation,
                "suggested_sql": rec.suggested_sql,
                "impact": rec.impact,
                "confidence": rec.confidence,
                "risk": rec.risk,
                "connection_id": conn_id,
                "source": "advisor",
            }
            insight_dicts.append(item)

        if insight_dicts:
            store.bulk_create(insight_dicts)

        logger.info(
            "Advisor cycle for %s: %d recommendations generated",
            conn_id, len(insight_dicts),
        )
        return insight_dicts

    async def _fetch_index_stats(self, connector: Any) -> list[dict[str, Any]]:
        """Fetch pg_stat_user_indexes for unused-index detection."""
        query = """
            SELECT
                schemaname,
                relname AS table_name,
                indexrelname AS index_name,
                idx_scan,
                pg_size_pretty(pg_relation_size(indexrelid)) AS idx_size
            FROM pg_stat_user_indexes
            ORDER BY idx_scan ASC
            LIMIT 50
        """
        rows = await connector.execute_read_only(query)
        return rows


_engine: AdvisorEngine | None = None
_engine_lock = threading.Lock()


def get_advisor_engine() -> AdvisorEngine:
    global _engine
    with _engine_lock:
        if _engine is None:
            _engine = AdvisorEngine()
        return _engine
