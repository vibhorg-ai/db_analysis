"""
Context/prompt trimming utilities for LLM token limits.

Converts raw pipeline context (schema metadata, agent outputs, etc.) into
a compact, structured text format that preserves all critical information
while using ~60% fewer tokens than raw JSON.
"""

from __future__ import annotations

import json
from typing import Any

CHARS_PER_TOKEN = 4

AGENT_OUTPUT_MAX_CHARS = 6000


def estimate_tokens(text: str) -> int:
    """Rough token count from character length."""
    if not text:
        return 0
    return len(text) // CHARS_PER_TOKEN


def _truncate_value(value: Any, max_chars: int) -> Any:
    """Recursively truncate strings, dicts, and lists to stay within max_chars."""
    if value is None:
        return None
    if isinstance(value, str):
        if len(value) <= max_chars:
            return value
        return value[:max_chars] + "...[truncated]"
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        remaining = max_chars
        for k, v in value.items():
            if remaining <= 0:
                break
            piece = _truncate_value(v, remaining // 2)
            result[k] = piece
            remaining -= len(json.dumps({k: piece}))
        return result
    if isinstance(value, list):
        result_list: list[Any] = []
        remaining = max_chars
        chunk = max(1, remaining // max(len(value), 1))
        for item in value:
            if remaining <= 0:
                break
            piece = _truncate_value(item, chunk)
            result_list.append(piece)
            remaining -= len(json.dumps(piece))
        return result_list
    return value


def _summarize_schema_metadata(tables: list[dict[str, Any]], max_chars: int = 25000) -> str:
    """Convert schema metadata list into compact text (~60% fewer tokens than JSON).

    Output format per table:
        Table schema.table_name: col1 (type), col2 (type), ...
          PK: col1, col2
          FK: fk_col -> target_table.ref_col
          IDX: index_name (col1, col2)
          ~50000 rows
    """
    if not tables:
        return "(no schema metadata available)"

    lines: list[str] = []
    char_count = 0

    for t in tables:
        tname = t.get("name") or t.get("table_name") or "?"

        cols = t.get("columns", [])
        col_parts: list[str] = []
        for c in cols:
            cname = c.get("name") or c.get("column_name") or "?"
            ctype = c.get("data_type") or c.get("type") or ""
            nullable = c.get("is_nullable")
            suffix = ""
            if nullable is False:
                suffix = " NOT NULL"
            col_parts.append(f"{cname} ({ctype}{suffix})" if ctype else cname)

        table_line = f"Table {tname}: {', '.join(col_parts)}"
        entry_lines = [table_line]

        pks = t.get("primary_key") or t.get("primary_keys") or []
        if pks:
            pk_str = ", ".join(pks) if isinstance(pks, list) else str(pks)
            entry_lines.append(f"  PK: {pk_str}")

        fks = t.get("foreign_keys", [])
        for fk in fks[:10]:
            fk_col = fk.get("column") or fk.get("constrained_columns") or ""
            if isinstance(fk_col, list):
                fk_col = ", ".join(fk_col)
            target = (
                fk.get("target_table")
                or fk.get("references_table")
                or fk.get("referred_table")
                or ""
            )
            ref_col = (
                fk.get("ref_column")
                or fk.get("references_column")
                or fk.get("referred_columns")
                or ""
            )
            if isinstance(ref_col, list):
                ref_col = ", ".join(ref_col)
            if fk_col and target:
                entry_lines.append(f"  FK: {fk_col} -> {target}.{ref_col}")

        indexes = t.get("indexes", [])
        for idx in indexes[:10]:
            idx_name = idx.get("name") or idx.get("index_name") or "?"
            idx_cols = idx.get("columns") or idx.get("column_names") or []
            if isinstance(idx_cols, list):
                idx_cols_str = ", ".join(idx_cols)
            else:
                idx_cols_str = str(idx_cols)
            entry_lines.append(f"  IDX: {idx_name} ({idx_cols_str})")

        row_count = t.get("row_count") or t.get("row_estimate")
        if row_count is not None and row_count > 0:
            entry_lines.append(f"  ~{row_count} rows")

        entry_text = "\n".join(entry_lines)
        new_count = char_count + len(entry_text) + 1

        if new_count > max_chars:
            remaining_tables = len(tables) - len(lines)
            if remaining_tables > 0:
                lines.append(f"... and {remaining_tables} more tables (truncated for token budget)")
            break

        lines.append(entry_text)
        char_count = new_count

    return "\n".join(lines)


def _summarize_report_contents(report_contents: list[Any]) -> str:
    """Replace full report content with compact summaries."""
    if not report_contents:
        return ""
    parts: list[str] = []
    preview_len = 2000
    for item in report_contents:
        if isinstance(item, dict):
            content = item.get("content", "")
            content_str = content if isinstance(content, str) else str(content)
            content_len = len(content_str)
            preview = content_str[:preview_len] + ("..." if content_len > preview_len else "")
            rid = item.get("id", "?")
            rtype = item.get("type", "?")
            parts.append(f"Report {rid} ({rtype}, {content_len} chars):\n{preview}")
        else:
            parts.append(str(item)[:500])
    return "\n\n".join(parts)


def _format_section(key: str, value: Any) -> str:
    """Format a single context key-value pair as a readable section."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        raw = value.get("raw_response")
        if raw and isinstance(raw, str):
            return raw[:AGENT_OUTPUT_MAX_CHARS] + (
                "...[truncated]" if len(raw) > AGENT_OUTPUT_MAX_CHARS else ""
            )
        try:
            dumped = json.dumps(value, default=str, indent=None)
        except (TypeError, ValueError):
            dumped = str(value)
        if len(dumped) > AGENT_OUTPUT_MAX_CHARS:
            return dumped[:AGENT_OUTPUT_MAX_CHARS] + "...[truncated]"
        return dumped
    if isinstance(value, list):
        try:
            dumped = json.dumps(value, default=str, indent=None)
        except (TypeError, ValueError):
            dumped = str(value)
        if len(dumped) > AGENT_OUTPUT_MAX_CHARS:
            return dumped[:AGENT_OUTPUT_MAX_CHARS] + "...[truncated]"
        return dumped
    return str(value)


def trim_context_for_llm(
    context: dict[str, Any],
    max_total_chars: int,
    reserved_chars: int = 500,
) -> str:
    """Build a structured context string safe for LLM context window.

    Uses compact summarization instead of raw JSON:
    - schema_metadata -> compact text (table/col/PK/FK/IDX/rows)
    - report_contents -> preview summaries
    - prior agent outputs -> truncated at 6000 chars
    - internal keys (prefixed with _) -> skipped
    """
    budget = max_total_chars - reserved_chars
    sections: list[str] = []
    char_count = 0

    for key, value in context.items():
        if key.startswith("_"):
            continue

        if key == "schema_metadata":
            if isinstance(value, list):
                section_body = _summarize_schema_metadata(value)
            elif isinstance(value, str):
                section_body = value[:25000] + ("...[truncated]" if len(value) > 25000 else "")
            else:
                section_body = str(value)[:25000]
        elif key == "report_contents" and isinstance(value, list):
            section_body = _summarize_report_contents(value)
        elif key in ("query", "engine"):
            section_body = str(value) if value else ""
        else:
            section_body = _format_section(key, value)

        if not section_body:
            continue

        header = key.replace("_", " ").title()
        section_text = f"## {header}\n\n{section_body}"

        if char_count + len(section_text) + 2 > budget:
            remaining = budget - char_count - 20
            if remaining > 100:
                sections.append(section_text[:remaining] + "...[truncated]")
            break

        sections.append(section_text)
        char_count += len(section_text) + 2

    return "\n\n".join(sections)
