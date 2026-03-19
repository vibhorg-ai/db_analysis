"""
Query plan simulator.

Uses EXPLAIN (not EXPLAIN ANALYZE) to compare execution plans
for current vs optimized queries without executing them.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class QueryPlanSimulator:
    """Compare query execution plans in sandbox mode."""

    async def compare_plans(
        self,
        connector: Any,
        engine: str,
        original_query: str,
        optimized_query: str,
    ) -> dict[str, Any]:
        if engine != "postgres":
            return {
                "simulation_type": "query_plan_comparison",
                "supported": False,
                "notes": f"EXPLAIN plan comparison only supported for PostgreSQL, not {engine}.",
            }

        original_plan = await self._get_plan(connector, original_query)
        optimized_plan = await self._get_plan(connector, optimized_query)

        original_cost = self._extract_cost(original_plan)
        optimized_cost = self._extract_cost(optimized_plan)

        improvement_pct = 0
        if original_cost > 0 and optimized_cost < original_cost:
            improvement_pct = round((1 - optimized_cost / original_cost) * 100, 1)

        return {
            "simulation_type": "query_plan_comparison",
            "supported": True,
            "original_plan": original_plan,
            "optimized_plan": optimized_plan,
            "original_cost": original_cost,
            "optimized_cost": optimized_cost,
            "improvement_pct": improvement_pct,
            "impact": "high" if improvement_pct > 30 else "medium" if improvement_pct > 10 else "low",
        }

    async def explain_query(
        self, connector: Any, engine: str, query: str
    ) -> dict[str, Any]:
        if engine != "postgres":
            return {"supported": False, "engine": engine}
        plan = await self._get_plan(connector, query)
        cost = self._extract_cost(plan)
        has_seq_scan = any("Seq Scan" in str(line) for line in plan)
        return {
            "plan": plan,
            "total_cost": cost,
            "has_sequential_scan": has_seq_scan,
        }

    async def _get_plan(self, connector: Any, query: str) -> list[str]:
        try:
            rows = await connector.execute_read_only(f"EXPLAIN {query}")
            return [row.get("QUERY PLAN", str(row)) for row in rows]
        except Exception as e:
            logger.debug("EXPLAIN failed: %s", e)
            return ["EXPLAIN failed: query could not be explained (check syntax or permissions)."]

    def _extract_cost(self, plan: list[str]) -> float:
        import re
        for line in plan:
            match = re.search(r"cost=[\d.]+\.\.([\d.]+)", str(line))
            if match:
                return float(match.group(1))
        return 0.0
