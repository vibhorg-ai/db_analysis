"""
Dependency impact simulator.

Uses the Dependency Mapping Engine to predict the blast radius
of schema changes before they are applied.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.graph.dependency_engine import get_dependency_engine

logger = logging.getLogger(__name__)


class DependencySimulator:
    """Analyze dependency impact of proposed changes."""

    def simulate_table_change(self, tables: list[str]) -> dict[str, Any]:
        dep = get_dependency_engine()
        impact = dep.analyze_schema_change_impact(tables)
        return {
            "simulation_type": "dependency_impact",
            "changed_tables": tables,
            "impacted_queries": impact.get("impacted_queries", []),
            "impacted_services": impact.get("impacted_services", []),
            "query_count": len(impact.get("impacted_queries", [])),
            "service_count": len(impact.get("impacted_services", [])),
            "risk": self._assess_risk(impact),
        }

    def simulate_column_removal(self, table: str, column: str) -> dict[str, Any]:
        dep = get_dependency_engine()
        col_impact = dep.get_column_impact(table, column)
        table_deps = dep.get_table_dependencies(table)

        return {
            "simulation_type": "column_removal_impact",
            "table": table,
            "column": column,
            "impacted_queries": col_impact.get("impacted_queries", []),
            "query_count": len(col_impact.get("impacted_queries", [])),
            "dependent_services": table_deps.get("services", []),
            "service_count": len(table_deps.get("services", [])),
            "risk": "high" if col_impact.get("impacted_queries") else "low",
        }

    def _assess_risk(self, impact: dict[str, Any]) -> str:
        queries = len(impact.get("impacted_queries", []))
        services = len(impact.get("impacted_services", []))
        if services > 2 or queries > 5:
            return "high"
        if services > 0 or queries > 2:
            return "medium"
        return "low"
