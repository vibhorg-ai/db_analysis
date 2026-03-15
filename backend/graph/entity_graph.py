"""
Build entity graph from schema metadata for schema relationship visualization.
"""

from __future__ import annotations


def _infer_table_type(table_name: str) -> str:
    """Infer table type from name: log, dim, fact, etc."""
    name_lower = (table_name or "").lower()
    if "log" in name_lower or "_log" in name_lower or "audit" in name_lower:
        return "log_table"
    if "dim" in name_lower or "dimension" in name_lower:
        return "dim_table"
    if "fact" in name_lower:
        return "fact_table"
    if "config" in name_lower or "settings" in name_lower:
        return "config_table"
    return "table"


def _normalize_schema(schema_metadata: list[dict] | dict) -> list[dict]:
    """Normalize input: handle dict with 'tables' key or list of tables."""
    if isinstance(schema_metadata, dict):
        tables = schema_metadata.get("tables", [])
        if isinstance(tables, dict):
            tables = list(tables.values()) if tables else []
        return tables if isinstance(tables, list) else []
    if isinstance(schema_metadata, list):
        return schema_metadata
    return []


def build_entity_graph(schema_metadata: list[dict] | dict) -> dict:
    """
    Build entity graph from schema metadata.

    Returns:
        {
            nodes: [{id, table_name, row_count, table_size, type}],
            edges: [{source, target, column, relationship, risk_flags}],
            schema_complexity_score: float,
            largest_tables: list,
            high_risk_relationships: list
        }
    """
    tables = _normalize_schema(schema_metadata)
    nodes: list[dict] = []
    edges: list[dict] = []
    table_names: set[str] = set()

    for tbl in tables:
        table_name = tbl.get("table_name") or tbl.get("name") or ""
        if not table_name or table_name in table_names:
            continue
        table_names.add(table_name)
        nodes.append(
            {
                "id": table_name,
                "table_name": table_name,
                "row_count": tbl.get("row_count", 0),
                "table_size": tbl.get("table_size") or tbl.get("size"),
                "type": _infer_table_type(table_name),
            }
        )

    for tbl in tables:
        table_name = tbl.get("table_name") or tbl.get("name") or ""
        if not table_name:
            continue
        for fk in tbl.get("foreign_keys", []):
            ref_table = fk.get("target_table") or ""
            if ref_table and ref_table in table_names:
                risk_flags: list[str] = []
                col = fk.get("column") or ""
                ref_col = fk.get("ref_column") or ""
                if not col or not ref_col:
                    risk_flags.append("incomplete_fk")
                edges.append(
                    {
                        "source": table_name,
                        "target": ref_table,
                        "column": col,
                        "relationship": fk.get("relationship_type", "one_to_many"),
                        "risk_flags": risk_flags,
                    }
                )

    num_tables = len(nodes)
    num_edges = len(edges)
    schema_complexity_score = min(
        10.0,
        num_tables * 0.5 + num_edges * 0.3,
    )

    largest_tables = sorted(
        nodes,
        key=lambda n: (n.get("row_count") or 0, n.get("table_size") or 0),
        reverse=True,
    )[:10]

    high_risk_relationships = [
        e for e in edges if e.get("risk_flags")
    ]

    return {
        "nodes": nodes,
        "edges": edges,
        "schema_complexity_score": round(schema_complexity_score, 1),
        "largest_tables": largest_tables,
        "high_risk_relationships": high_risk_relationships,
    }
