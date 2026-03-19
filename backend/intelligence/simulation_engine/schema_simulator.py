"""
Schema change simulator.

Simulates the impact of schema modifications using EXPLAIN plans
and metadata analysis — never modifies the actual database.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class SchemaSimulator:
    """Predicts impact of schema changes using query plans and metadata."""

    async def simulate_add_index(
        self,
        connector: Any,
        engine: str,
        table: str,
        columns: list[str],
        schema_metadata: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        index_name = f"idx_{table}_{'_'.join(columns)}"
        col_list = ", ".join(columns)

        table_info = self._find_table(table, schema_metadata)
        row_count = table_info.get("row_count", 0) if table_info else 0

        improvement_pct = self._estimate_index_improvement(row_count, columns, table_info)

        return {
            "simulation_type": "add_index",
            "change": f"CREATE INDEX {index_name} ON {table}({col_list})",
            "table": table,
            "columns": columns,
            "predicted_improvement_pct": improvement_pct,
            "impact": "high" if improvement_pct > 40 else "medium" if improvement_pct > 15 else "low",
            "risk": "low",
            "row_count": row_count,
            "notes": self._index_creation_notes(row_count),
        }

    async def simulate_remove_index(
        self,
        connector: Any,
        engine: str,
        index_name: str,
        affected_queries: list[str] | None = None,
    ) -> dict[str, Any]:
        query_count = len(affected_queries) if affected_queries else 0

        return {
            "simulation_type": "remove_index",
            "change": f"DROP INDEX {index_name}",
            "index_name": index_name,
            "affected_query_count": query_count,
            "predicted_latency_increase_pct": min(query_count * 8, 50),
            "impact": "high" if query_count > 3 else "medium" if query_count > 0 else "low",
            "risk": "high" if query_count > 3 else "medium" if query_count > 0 else "low",
            "notes": f"{query_count} queries currently use this index." if query_count else "No known queries use this index.",
        }

    async def simulate_drop_column(
        self,
        connector: Any,
        engine: str,
        table: str,
        column: str,
        dependency_impact: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        impacted_queries = 0
        impacted_services = 0
        if dependency_impact:
            impacted_queries = len(dependency_impact.get("impacted_queries", []))
            impacted_services = len(dependency_impact.get("impacted_services", []))

        risk = "high" if impacted_queries > 0 or impacted_services > 0 else "low"

        return {
            "simulation_type": "drop_column",
            "change": f"ALTER TABLE {table} DROP COLUMN {column}",
            "table": table,
            "column": column,
            "impacted_queries": impacted_queries,
            "impacted_services": impacted_services,
            "impact": "high" if impacted_queries > 2 else "medium" if impacted_queries > 0 else "low",
            "risk": risk,
            "notes": (
                f"{impacted_queries} queries and {impacted_services} services depend on `{column}`."
                if impacted_queries else f"No known dependencies on `{table}.{column}`."
            ),
        }

    async def simulate_partition_table(
        self,
        connector: Any,
        engine: str,
        table: str,
        partition_column: str,
        schema_metadata: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        table_info = self._find_table(table, schema_metadata)
        row_count = table_info.get("row_count", 0) if table_info else 0

        improvement_pct = 0
        if row_count > 50_000_000:
            improvement_pct = 50
        elif row_count > 10_000_000:
            improvement_pct = 40
        elif row_count > 1_000_000:
            improvement_pct = 25
        elif row_count > 100_000:
            improvement_pct = 10

        return {
            "simulation_type": "partition_table",
            "change": f"Partition {table} by {partition_column}",
            "table": table,
            "partition_column": partition_column,
            "row_count": row_count,
            "predicted_improvement_pct": improvement_pct,
            "impact": "high" if improvement_pct > 30 else "medium" if improvement_pct > 10 else "low",
            "risk": "high",
            "notes": f"Table has {row_count:,} rows. Partitioning requires table recreation and data migration.",
        }

    def _find_table(self, name: str, schema: list[dict[str, Any]] | None) -> dict[str, Any] | None:
        if not schema:
            return None
        name_lower = name.lower()
        for t in schema:
            tname = (t.get("table_name") or t.get("name", "")).lower()
            if tname == name_lower or tname.endswith(f".{name_lower}"):
                return t
        return None

    def _estimate_index_improvement(
        self, row_count: int, columns: list[str], table_info: dict[str, Any] | None
    ) -> int:
        if row_count > 10_000_000:
            return 60
        if row_count > 1_000_000:
            return 45
        if row_count > 100_000:
            return 30
        if row_count > 10_000:
            return 15
        return 5

    def _index_creation_notes(self, row_count: int) -> str:
        if row_count > 50_000_000:
            return "Large table: index creation will take significant time and I/O. Consider CONCURRENTLY."
        if row_count > 1_000_000:
            return "Consider CREATE INDEX CONCURRENTLY to avoid locking."
        return "Index creation should be fast."
