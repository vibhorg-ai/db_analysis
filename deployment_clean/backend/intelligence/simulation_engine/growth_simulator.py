"""
Growth simulator.

Predicts the impact of data growth on storage, query performance,
and resource usage based on current statistics.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class GrowthSimulator:
    """Predict impact of table/database growth."""

    async def simulate_growth(
        self,
        connector: Any,
        engine: str,
        table: str,
        target_rows: int,
        schema_metadata: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        current_rows = 0
        current_size_bytes = 0
        table_found = False

        if engine == "postgres":
            current_rows, current_size_bytes = await self._get_postgres_table_stats(
                connector, table
            )
            if current_rows > 0 or current_size_bytes > 0:
                table_found = True
            # Fallback: use schema_metadata (same source as partition sim) when stats return 0
            if not table_found and schema_metadata:
                for t in schema_metadata:
                    tname = (t.get("table_name") or t.get("name", "")).lower()
                    if tname == table.lower() or tname.endswith(f".{table.lower()}"):
                        current_rows = t.get("row_count", 0) or 0
                        table_found = True
                        break
        elif schema_metadata:
            for t in schema_metadata:
                tname = (t.get("table_name") or t.get("name", "")).lower()
                if tname == table.lower() or tname.endswith(f".{table.lower()}"):
                    current_rows = t.get("row_count", 0) or 0
                    table_found = True
                    break

        # Table not in schema and no stats: cannot determine row count
        if not table_found and current_rows == 0:
            return {
                "simulation_type": "growth",
                "table": table,
                "error": f"Could not determine current row count for `{table}`. Ensure the table exists and the connection can read its metadata.",
            }

        # Allow empty tables: simulate growth from 0 to target_rows
        if current_rows == 0 and target_rows <= 0:
            return {
                "simulation_type": "growth",
                "table": table,
                "error": "Target rows must be greater than 0 for growth simulation.",
            }

        growth_factor = target_rows / current_rows if current_rows > 0 else float(target_rows)
        predicted_size_bytes = int(current_size_bytes * growth_factor) if current_size_bytes else 0
        predicted_size_readable = self._format_bytes(predicted_size_bytes)

        latency_increase_pct = self._estimate_latency_impact(current_rows, target_rows)

        recommendations: list[str] = []
        if current_rows == 0:
            recommendations.append("Table is currently empty. Simulation shows impact of adding rows.")
        if target_rows > 50_000_000:
            recommendations.append("Consider table partitioning by date or range.")
        if target_rows > 10_000_000:
            recommendations.append("Ensure all filter columns are indexed.")
        if growth_factor > 10 and current_rows > 0:
            recommendations.append("Review query patterns — sequential scans will degrade significantly.")
        if predicted_size_bytes > 100 * 1024**3:
            recommendations.append("Storage may exceed 100 GB. Plan capacity accordingly.")

        return {
            "simulation_type": "growth",
            "table": table,
            "current_rows": current_rows,
            "target_rows": target_rows,
            "growth_factor": round(growth_factor, 1),
            "current_size": self._format_bytes(current_size_bytes),
            "predicted_size": predicted_size_readable,
            "predicted_latency_increase_pct": latency_increase_pct,
            "impact": "high" if latency_increase_pct > 30 else "medium" if latency_increase_pct > 10 else "low",
            "risk": "high" if growth_factor > 10 else "medium" if growth_factor > 3 else "low",
            "recommendations": recommendations,
        }

    async def _get_postgres_table_stats(
        self, connector: Any, table: str
    ) -> tuple[int, int]:
        """Get row count and size from pg_stat_user_tables. Uses parameterized query and case-insensitive match."""
        try:
            import re
            short_name = table.split(".")[-1].strip()
            if not short_name or not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", short_name):
                return 0, 0
            # Parameterized query + ILIKE so quoted/mixed-case table names (e.g. "Abi_Invoice") are found
            query = (
                "SELECT n_live_tup AS row_count, "
                "pg_total_relation_size(quote_ident(schemaname) || '.' || quote_ident(relname)) AS total_bytes "
                "FROM pg_stat_user_tables "
                "WHERE relname ILIKE $1 "
                "LIMIT 1"
            )
            rows = await connector.execute_read_only(query, short_name)
            if rows:
                return int(rows[0].get("row_count", 0) or 0), int(rows[0].get("total_bytes", 0) or 0)
        except Exception as e:
            logger.debug("Growth stats fetch failed: %s", e)
        return 0, 0

    def _estimate_latency_impact(self, current: int, target: int) -> int:
        if current == 0:
            return 0
        ratio = target / current
        if ratio <= 1:
            return 0
        if ratio <= 2:
            return 10
        if ratio <= 5:
            return 25
        if ratio <= 10:
            return 40
        return min(int(ratio * 4), 80)

    @staticmethod
    def _format_bytes(b: int) -> str:
        if b <= 0:
            return "unknown"
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if b < 1024:
                return f"{b:.1f} {unit}"
            b /= 1024
        return f"{b:.1f} PB"
