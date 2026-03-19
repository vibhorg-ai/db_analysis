"""
Recommendation engine for the Autonomous Database Advisor.

Analyzes schema metadata, index usage, health metrics, and dependency graphs
to produce scored recommendations across categories:
- Query optimization
- Missing/unused indexes
- Schema improvements
- Dependency risks
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Recommendation:
    category: str  # performance, schema, risk, workload
    title: str
    description: str
    recommendation: str
    suggested_sql: str | None = None
    impact: str = "medium"
    confidence: float = 50.0
    risk: str = "low"


class RecommendationEngine:
    """Generates recommendations from raw analysis data."""

    def generate(
        self,
        *,
        schema: list[dict[str, Any]] | None = None,
        health: dict[str, Any] | None = None,
        workload: dict[str, Any] | None = None,
        dependencies: dict[str, Any] | None = None,
        index_stats: list[dict[str, Any]] | None = None,
    ) -> list[Recommendation]:
        recs: list[Recommendation] = []

        if schema:
            recs.extend(self._schema_recommendations(schema))

        if health:
            recs.extend(self._health_recommendations(health))

        if workload:
            recs.extend(self._workload_recommendations(workload, schema))

        if index_stats:
            recs.extend(self._index_recommendations(index_stats))

        if dependencies and schema:
            recs.extend(self._dependency_risk_recommendations(dependencies, schema))

        return recs

    def _schema_recommendations(self, schema: list[dict[str, Any]]) -> list[Recommendation]:
        recs: list[Recommendation] = []
        for table in schema:
            tname = table.get("table_name", table.get("name", "?"))
            row_count = table.get("row_count", 0) or 0
            columns = table.get("columns", [])
            pks = table.get("primary_key")
            fks = table.get("foreign_keys", [])

            if row_count > 10_000_000 and not any("partition" in str(c).lower() for c in columns):
                recs.append(Recommendation(
                    category="schema",
                    title=f"Large table `{tname}` may benefit from partitioning",
                    description=f"Table `{tname}` contains {row_count:,} rows.",
                    recommendation=f"Consider partitioning `{tname}` by a date or range column to improve query performance.",
                    impact="high",
                    confidence=75.0,
                    risk="medium",
                ))

            if not pks and row_count > 0:
                recs.append(Recommendation(
                    category="schema",
                    title=f"Table `{tname}` has no primary key",
                    description=f"Table `{tname}` lacks a primary key constraint.",
                    recommendation=f"Add a primary key to `{tname}` for data integrity and join performance.",
                    impact="medium",
                    confidence=90.0,
                    risk="low",
                ))

            if len(columns) > 50:
                recs.append(Recommendation(
                    category="schema",
                    title=f"Table `{tname}` has many columns ({len(columns)})",
                    description=f"Wide tables can hurt scan performance.",
                    recommendation=f"Consider normalizing `{tname}` or splitting into related tables.",
                    impact="medium",
                    confidence=60.0,
                    risk="medium",
                ))

            for fk in fks:
                fk_col = fk.get("column", "")
                if fk_col:
                    has_index = False
                    for col in columns:
                        col_name = col.get("name", col.get("column_name", ""))
                        if col_name == fk_col:
                            has_index = True
                            break
                    if not has_index:
                        recs.append(Recommendation(
                            category="performance",
                            title=f"FK column `{tname}.{fk_col}` may need an index",
                            description=f"Foreign key column `{fk_col}` on `{tname}` is used in joins but may lack a dedicated index.",
                            recommendation=f"Add index on `{tname}({fk_col})`.",
                            suggested_sql=f"CREATE INDEX idx_{tname}_{fk_col} ON {tname}({fk_col});",
                            impact="high",
                            confidence=80.0,
                            risk="low",
                        ))
        return recs

    def _health_recommendations(self, health: dict[str, Any]) -> list[Recommendation]:
        recs: list[Recommendation] = []
        raw_metrics = health.get("metrics", {})
        alerts = health.get("alerts", [])
        score = health.get("score", 100)

        metrics_items: list[tuple[str, Any]] = []
        if isinstance(raw_metrics, dict):
            metrics_items = list(raw_metrics.items())
        elif isinstance(raw_metrics, list):
            for m in raw_metrics:
                if isinstance(m, dict) and "name" in m:
                    metrics_items.append((m["name"], m.get("value")))
                elif isinstance(m, dict):
                    metrics_items.extend(m.items())

        for name, value in metrics_items:
            if name == "cache_hit_ratio" and value is not None and value < 95:
                recs.append(Recommendation(
                    category="performance",
                    title="Low cache hit ratio",
                    description=f"Cache hit ratio is {value:.1f}%. Target is 99%+.",
                    recommendation="Increase `shared_buffers` or review query patterns that bypass the buffer cache.",
                    impact="high",
                    confidence=85.0,
                    risk="low",
                ))
            elif name == "dead_tuples_ratio" and value is not None and value > 10:
                recs.append(Recommendation(
                    category="performance",
                    title="High dead tuple ratio",
                    description=f"Dead tuple ratio is {value:.1f}%. This degrades scan performance.",
                    recommendation="Run VACUUM ANALYZE on affected tables or tune autovacuum settings.",
                    impact="medium",
                    confidence=90.0,
                    risk="low",
                ))
            elif name == "locks_waiting" and value is not None and value > 0:
                recs.append(Recommendation(
                    category="performance",
                    title=f"{int(value)} queries waiting on locks",
                    description="Lock contention detected. Queries are blocked.",
                    recommendation="Investigate long-running transactions and consider query optimization to reduce lock hold time.",
                    impact="high",
                    confidence=80.0,
                    risk="medium",
                ))

        if score < 50:
            recs.append(Recommendation(
                category="risk",
                title="Critical health score",
                description=f"Database health score is {score}/100.",
                recommendation="Immediate investigation required. Review alerts and metrics.",
                impact="high",
                confidence=95.0,
                risk="high",
            ))
        return recs

    def _workload_recommendations(
        self, workload: dict[str, Any], schema: list[dict[str, Any]] | None
    ) -> list[Recommendation]:
        recs: list[Recommendation] = []

        for fq in workload.get("frequent_queries", []):
            count = fq.get("execution_count", 0)
            avg_ms = fq.get("avg_duration_ms", 0)
            pattern = fq.get("query_pattern", "")
            if count > 1000 and avg_ms > 100:
                recs.append(Recommendation(
                    category="performance",
                    title="High-frequency slow query detected",
                    description=f"Query pattern executed {count:,} times with avg {avg_ms:.0f}ms.\n`{pattern[:150]}`",
                    recommendation="Analyze query plan with EXPLAIN ANALYZE. Consider adding indexes on filter/join columns.",
                    impact="high",
                    confidence=85.0,
                    risk="low",
                ))

        for sp in workload.get("slow_patterns", [])[:5]:
            dur = sp.get("duration_ms", 0)
            pattern = sp.get("query_pattern", "")
            if dur > 5000:
                recs.append(Recommendation(
                    category="performance",
                    title="Very slow query detected",
                    description=f"Query took {dur:.0f}ms.\n`{pattern[:150]}`",
                    recommendation="Review execution plan. Consider index creation or query rewrite.",
                    impact="high",
                    confidence=70.0,
                    risk="low",
                ))

        trend = workload.get("performance_trend", {})
        min_score = trend.get("min_health_score", 100)
        if min_score < 50 and trend.get("data_points", 0) > 3:
            recs.append(Recommendation(
                category="risk",
                title="Health score dropped critically in the last 24 hours",
                description=f"Minimum health score was {min_score}/100.",
                recommendation="Review performance snapshots to identify the root cause.",
                impact="high",
                confidence=80.0,
                risk="high",
            ))

        return recs

    def _index_recommendations(self, index_stats: list[dict[str, Any]]) -> list[Recommendation]:
        recs: list[Recommendation] = []
        for stat in index_stats:
            idx_name = stat.get("index_name", "?")
            scans = stat.get("idx_scan", 0)
            size = stat.get("idx_size", "")
            table = stat.get("table_name", "?")
            if scans == 0:
                recs.append(Recommendation(
                    category="schema",
                    title=f"Unused index `{idx_name}` on `{table}`",
                    description=f"Index `{idx_name}` has 0 scans. Size: {size}.",
                    recommendation=f"Consider dropping `{idx_name}` to save storage and reduce write overhead.",
                    suggested_sql=f"DROP INDEX IF EXISTS {idx_name};",
                    impact="low",
                    confidence=70.0,
                    risk="medium",
                ))
        return recs

    def _dependency_risk_recommendations(
        self, deps: dict[str, Any], schema: list[dict[str, Any]]
    ) -> list[Recommendation]:
        recs: list[Recommendation] = []
        services = deps.get("services", {})
        queries = deps.get("queries", {})

        table_refs: dict[str, int] = {}
        for qid, qdata in queries.items():
            for t in qdata.get("tables_read", []) + qdata.get("tables_written", []):
                table_refs[t] = table_refs.get(t, 0) + 1

        for tname, ref_count in table_refs.items():
            if ref_count >= 5:
                svc_count = sum(
                    1 for s in services.values()
                    if any(qid in s.get("queries", []) for qid in queries
                           if tname in queries[qid].get("tables_read", []) + queries[qid].get("tables_written", []))
                )
                recs.append(Recommendation(
                    category="risk",
                    title=f"High-dependency table `{tname}`",
                    description=f"`{tname}` is referenced by {ref_count} queries across {svc_count} services.",
                    recommendation=f"Schema changes to `{tname}` carry high blast radius. Test thoroughly before modifying.",
                    impact="high",
                    confidence=85.0,
                    risk="high",
                ))
        return recs
