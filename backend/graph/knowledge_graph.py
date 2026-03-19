"""
In-memory knowledge graph representing the database ecosystem.
Node types: table, column, index, query, workload, metric, issue
Edge types: HAS_COLUMN, HAS_INDEX, INDEXES_COLUMN, FOREIGN_KEY, READS, WRITES, DEPENDS_ON, RELATES_TO
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class KGNode:
    """Knowledge graph node."""

    id: str
    node_type: str  # table, column, index, query, workload, metric, issue
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class KGEdge:
    """Knowledge graph edge."""

    source_id: str
    target_id: str
    edge_type: str  # HAS_COLUMN, HAS_INDEX, FOREIGN_KEY, READS, WRITES, DEPENDS_ON, RELATES_TO
    properties: dict[str, Any] = field(default_factory=dict)


class KnowledgeGraph:
    """In-memory knowledge graph for database ecosystem."""

    def __init__(self) -> None:
        self._nodes: dict[str, KGNode] = {}
        self._edges: list[KGEdge] = []
        self._lock = threading.Lock()

    def add_node(
        self,
        node_id: str,
        node_type: str,
        properties: dict[str, Any] | None = None,
    ) -> KGNode:
        """Add or update a node. Returns the node."""
        node = KGNode(id=node_id, node_type=node_type, properties=properties or {})
        with self._lock:
            self._nodes[node_id] = node
        return node

    def get_node(self, node_id: str) -> KGNode | None:
        """Return node by id, or None."""
        with self._lock:
            return self._nodes.get(node_id)

    def remove_node(self, node_id: str) -> bool:
        """Remove node and its edges. Returns True if removed."""
        with self._lock:
            if node_id not in self._nodes:
                return False
            del self._nodes[node_id]
            self._edges = [
                e for e in self._edges if e.source_id != node_id and e.target_id != node_id
            ]
        return True

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        properties: dict[str, Any] | None = None,
    ) -> KGEdge:
        """Add an edge. Returns the edge."""
        edge = KGEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            properties=properties or {},
        )
        with self._lock:
            self._edges.append(edge)
        return edge

    def get_edges(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        edge_type: str | None = None,
    ) -> list[KGEdge]:
        """Return edges matching optional filters."""
        with self._lock:
            result = list(self._edges)
        if source_id is not None:
            result = [e for e in result if e.source_id == source_id]
        if target_id is not None:
            result = [e for e in result if e.target_id == target_id]
        if edge_type is not None:
            result = [e for e in result if e.edge_type == edge_type]
        return result

    def get_neighbors(
        self,
        node_id: str,
        edge_type: str | None = None,
    ) -> list[KGNode]:
        """Return neighboring nodes (outgoing and incoming)."""
        with self._lock:
            neighbor_ids: set[str] = set()
            for e in self._edges:
                if edge_type is not None and e.edge_type != edge_type:
                    continue
                other_id: str | None = None
                if e.source_id == node_id:
                    other_id = e.target_id
                elif e.target_id == node_id:
                    other_id = e.source_id
                if other_id and other_id in self._nodes:
                    neighbor_ids.add(other_id)
            return [self._nodes[nid] for nid in neighbor_ids]

    def get_nodes_by_type(self, node_type: str) -> list[KGNode]:
        """Return all nodes of the given type."""
        with self._lock:
            return [n for n in self._nodes.values() if n.node_type == node_type]

    def clear(self) -> None:
        """Remove all nodes and edges."""
        with self._lock:
            self._nodes.clear()
            self._edges.clear()

    def populate_from_schema(self, schema_metadata: list[dict[str, Any]]) -> None:
        """Build graph nodes/edges from schema metadata (tables, columns, FKs, indexes)."""
        self.clear()
        seen: set[str] = set()
        table_names: set[str] = set()

        for tbl in schema_metadata:
            table_name = tbl.get("table_name") or tbl.get("name") or ""
            if not table_name or table_name in seen:
                continue
            seen.add(table_name)
            table_names.add(table_name)
            self.add_node(
                table_name,
                "table",
                {
                    "schema": tbl.get("schema", ""),
                    "row_count": tbl.get("row_count", 0),
                    "table_size": tbl.get("table_size"),
                },
            )

        for tbl in schema_metadata:
            table_name = tbl.get("table_name") or tbl.get("name") or ""
            if not table_name:
                continue

            for col in tbl.get("columns", []):
                col_name = col.get("name") or ""
                if not col_name:
                    continue
                col_id = f"{table_name}.{col_name}"
                if col_id not in seen:
                    seen.add(col_id)
                    self.add_node(
                        col_id,
                        "column",
                        {
                            "data_type": col.get("data_type", ""),
                            "is_nullable": col.get("is_nullable", False),
                        },
                    )
                self.add_edge(table_name, col_id, "HAS_COLUMN", {"ordinal": col.get("ordinal_position")})

            for idx in tbl.get("indexes", []):
                idx_name = idx.get("name") or idx.get("index_name") or ""
                if idx_name:
                    idx_id = f"{table_name}::{idx_name}"
                    if idx_id not in seen:
                        seen.add(idx_id)
                        self.add_node(idx_id, "index", {"columns": idx.get("columns", [])})
                    self.add_edge(table_name, idx_id, "HAS_INDEX")
                    for col_name in idx.get("columns", []):
                        if col_name:
                            col_id = f"{table_name}.{col_name}"
                            if col_id in self._nodes:
                                self.add_edge(idx_id, col_id, "INDEXES_COLUMN")

            for fk in tbl.get("foreign_keys", []):
                ref_table = fk.get("target_table") or ""
                if ref_table and ref_table in table_names:
                    self.add_edge(
                        table_name,
                        ref_table,
                        "FOREIGN_KEY",
                        {
                            "column": fk.get("column"),
                            "ref_column": fk.get("ref_column"),
                            "relationship_type": fk.get("relationship_type", "one_to_many"),
                        },
                    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize graph for API/UI."""
        with self._lock:
            nodes = [
                {
                    "id": n.id,
                    "node_type": n.node_type,
                    "properties": dict(n.properties),
                }
                for n in self._nodes.values()
            ]
            edges = [
                {
                    "source_id": e.source_id,
                    "target_id": e.target_id,
                    "edge_type": e.edge_type,
                    "properties": dict(e.properties),
                }
                for e in self._edges
            ]
        return {"nodes": nodes, "edges": edges}

    def summary(self) -> dict[str, Any]:
        """Return node/edge counts and basic stats."""
        with self._lock:
            counts: dict[str, int] = {}
            for n in self._nodes.values():
                counts[n.node_type] = counts.get(n.node_type, 0) + 1
            edge_counts: dict[str, int] = {}
            for e in self._edges:
                edge_counts[e.edge_type] = edge_counts.get(e.edge_type, 0) + 1
        return {
            "node_count": len(self._nodes),
            "edge_count": len(self._edges),
            "nodes_by_type": counts,
            "edges_by_type": edge_counts,
        }


_kg: KnowledgeGraph | None = None
_kg_lock = threading.Lock()


def get_knowledge_graph() -> KnowledgeGraph:
    """Module singleton for KnowledgeGraph."""
    global _kg
    with _kg_lock:
        if _kg is None:
            _kg = KnowledgeGraph()
        return _kg
