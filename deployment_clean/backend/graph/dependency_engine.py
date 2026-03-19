"""
Tracks dependencies between database objects and application usage.
Maps SERVICE -> QUERY -> TABLE -> COLUMN -> INDEX.
"""

from __future__ import annotations

import threading
from typing import Any


class DependencyEngine:
    """Maps relationships: SERVICE->QUERY->TABLE->COLUMN->INDEX."""

    def __init__(self) -> None:
        self._services: dict[str, dict[str, Any]] = {}  # service_id -> {name, queries: [query_ids]}
        self._queries: dict[str, dict[str, Any]] = {}  # query_id -> {sql, tables_read, tables_written}
        self._service_query_links: set[tuple[str, str]] = set()  # (service_id, query_id)
        self._lock = threading.Lock()

    def register_service(self, service_id: str, name: str) -> None:
        """Register or update a service."""
        with self._lock:
            self._services[service_id] = {
                "name": name,
                "queries": self._services.get(service_id, {}).get("queries", []),
            }

    def register_query(
        self,
        query_id: str,
        sql: str,
        tables_read: list[str],
        tables_written: list[str],
    ) -> None:
        """Register or update a query."""
        with self._lock:
            self._queries[query_id] = {
                "sql": sql,
                "tables_read": list(tables_read),
                "tables_written": list(tables_written),
            }

    def link_service_query(self, service_id: str, query_id: str) -> None:
        """Link a service to a query."""
        with self._lock:
            self._service_query_links.add((service_id, query_id))
            if service_id not in self._services:
                self._services[service_id] = {"name": service_id, "queries": []}
            qs = self._services[service_id].get("queries", [])
            if query_id not in qs:
                qs.append(query_id)
                self._services[service_id]["queries"] = qs

    def get_table_dependencies(self, table_name: str) -> dict[str, Any]:
        """What services and queries depend on this table?"""
        with self._lock:
            queries_using: list[str] = []
            services_using: list[str] = []
            for qid, q in self._queries.items():
                read = q.get("tables_read", [])
                written = q.get("tables_written", [])
                if table_name in read or table_name in written:
                    queries_using.append(qid)
            for sid, qid in self._service_query_links:
                if qid in queries_using and sid not in services_using:
                    services_using.append(sid)
            return {
                "table": table_name,
                "queries": queries_using,
                "services": services_using,
            }

    def get_column_impact(self, table_name: str, column_name: str) -> dict[str, Any]:
        """What queries might break if this column changes?"""
        with self._lock:
            impacted_queries: list[dict] = []
            for qid, q in self._queries.items():
                read = q.get("tables_read", [])
                written = q.get("tables_written", [])
                if table_name not in read and table_name not in written:
                    continue
                sql = (q.get("sql") or "").upper()
                col_upper = (column_name or "").upper()
                if col_upper and col_upper in sql:
                    impacted_queries.append({"query_id": qid, "sql_preview": (q.get("sql") or "")[:200]})
            return {
                "table": table_name,
                "column": column_name,
                "impacted_queries": impacted_queries,
            }

    def get_service_dependencies(self, service_id: str) -> dict[str, Any]:
        """What tables and columns does this service depend on?"""
        with self._lock:
            tables: set[str] = set()
            query_ids = []
            for sid, qid in self._service_query_links:
                if sid == service_id:
                    query_ids.append(qid)
            for qid in query_ids:
                q = self._queries.get(qid, {})
                tables.update(q.get("tables_read", []))
                tables.update(q.get("tables_written", []))
            return {
                "service_id": service_id,
                "service_name": self._services.get(service_id, {}).get("name", service_id),
                "queries": query_ids,
                "tables": sorted(tables),
            }

    def analyze_schema_change_impact(self, changed_tables: list[str]) -> dict[str, Any]:
        """Predict impact of schema changes on services and queries."""
        with self._lock:
            impacted_queries: set[str] = set()
            impacted_services: set[str] = set()
            for t in changed_tables:
                for qid, q in self._queries.items():
                    read = q.get("tables_read", [])
                    written = q.get("tables_written", [])
                    if t in read or t in written:
                        impacted_queries.add(qid)
                for sid, qid in self._service_query_links:
                    if qid in impacted_queries:
                        impacted_services.add(sid)
            return {
                "changed_tables": changed_tables,
                "impacted_queries": list(impacted_queries),
                "impacted_services": list(impacted_services),
            }

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API/UI."""
        with self._lock:
            return {
                "services": dict(self._services),
                "queries": dict(self._queries),
                "service_query_links": [{"service": s, "query": q} for s, q in self._service_query_links],
            }


_engine: DependencyEngine | None = None
_engine_lock = threading.Lock()


def get_dependency_engine() -> DependencyEngine:
    """Module singleton for DependencyEngine."""
    global _engine
    with _engine_lock:
        if _engine is None:
            _engine = DependencyEngine()
        return _engine
