"""
Main simulation engine — entry point for all "what-if" scenarios.

Dispatches to specialized simulators based on the change type.
All simulations are read-only; they never modify the database.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from .schema_simulator import SchemaSimulator
from .query_plan_simulator import QueryPlanSimulator
from .dependency_simulator import DependencySimulator
from .growth_simulator import GrowthSimulator

logger = logging.getLogger(__name__)


@dataclass
class SimulationResult:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    simulation_type: str = ""
    input_description: str = ""
    result: dict[str, Any] = field(default_factory=dict)
    connection_id: str = ""


class SimulationEngine:
    """Unified interface for running database simulations."""

    def __init__(self) -> None:
        self._schema_sim = SchemaSimulator()
        self._plan_sim = QueryPlanSimulator()
        self._dep_sim = DependencySimulator()
        self._growth_sim = GrowthSimulator()
        self._history: list[SimulationResult] = []
        self._lock = threading.Lock()

    async def simulate(
        self,
        *,
        change_type: str,
        connector: Any,
        engine: str,
        connection_id: str = "",
        table: str = "",
        column: str = "",
        columns: list[str] | None = None,
        index_name: str = "",
        partition_column: str = "",
        target_rows: int = 0,
        original_query: str = "",
        optimized_query: str = "",
        schema_metadata: list[dict[str, Any]] | None = None,
    ) -> SimulationResult:
        """
        Run a simulation. change_type must be one of:
        add_index, remove_index, drop_column, partition_table,
        query_comparison, growth, dependency_impact
        """
        result_data: dict[str, Any]

        if change_type == "add_index":
            result_data = await self._schema_sim.simulate_add_index(
                connector, engine, table, columns or [], schema_metadata
            )
        elif change_type == "remove_index":
            result_data = await self._schema_sim.simulate_remove_index(
                connector, engine, index_name
            )
        elif change_type == "drop_column":
            dep_impact = self._dep_sim.simulate_column_removal(table, column)
            result_data = await self._schema_sim.simulate_drop_column(
                connector, engine, table, column, dep_impact
            )
        elif change_type == "partition_table":
            result_data = await self._schema_sim.simulate_partition_table(
                connector, engine, table, partition_column, schema_metadata
            )
        elif change_type == "query_comparison":
            result_data = await self._plan_sim.compare_plans(
                connector, engine, original_query, optimized_query
            )
        elif change_type == "growth":
            result_data = await self._growth_sim.simulate_growth(
                connector, engine, table, target_rows, schema_metadata
            )
        elif change_type == "dependency_impact":
            tables = [table] if table else []
            result_data = self._dep_sim.simulate_table_change(tables)
        else:
            result_data = {"error": f"Unknown simulation type: {change_type}"}

        sim_result = SimulationResult(
            simulation_type=change_type,
            input_description=self._describe_input(change_type, table, column, columns, index_name, partition_column, target_rows),
            result=result_data,
            connection_id=connection_id,
        )

        with self._lock:
            self._history.append(sim_result)
            if len(self._history) > 100:
                self._history = self._history[-100:]

        return sim_result

    def get_history(self, limit: int = 20) -> list[SimulationResult]:
        with self._lock:
            return list(reversed(self._history[-limit:]))

    def _describe_input(
        self, change_type: str, table: str, column: str,
        columns: list[str] | None, index_name: str,
        partition_column: str, target_rows: int,
    ) -> str:
        if change_type == "add_index" and columns:
            return f"Add index on {table}({', '.join(columns)})"
        if change_type == "remove_index":
            return f"Remove index {index_name}"
        if change_type == "drop_column":
            return f"Drop column {table}.{column}"
        if change_type == "partition_table":
            return f"Partition {table} by {partition_column}"
        if change_type == "growth":
            return f"Grow {table} to {target_rows:,} rows"
        if change_type == "query_comparison":
            return "Compare query execution plans"
        if change_type == "dependency_impact":
            return f"Dependency impact on {table}"
        return change_type


_engine: SimulationEngine | None = None
_engine_lock = threading.Lock()


def get_simulation_engine() -> SimulationEngine:
    global _engine
    with _engine_lock:
        if _engine is None:
            _engine = SimulationEngine()
        return _engine
