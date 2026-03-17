"""
HTML report parser for DB Analyzer AI v5.

Handles two report formats:
1. PGAWR reports: traditional HTML with <table> elements containing DB stats
2. Admin/ctlg/blc reports: JS-driven HTML with embedded `const data={...}` JSON

Extracts content into plain-text summaries suitable for LLM context.
"""

from __future__ import annotations

import json
import logging
import re
from html.parser import HTMLParser
from typing import Any

logger = logging.getLogger(__name__)

_MAX_TABLE_ROWS = 50
_MAX_JSON_DATASETS = 10
_MAX_DATASET_ROWS = 30


class _TableExtractor(HTMLParser):
    """Extracts headings and HTML tables into structured data."""

    def __init__(self) -> None:
        super().__init__()
        self._tables: list[dict[str, Any]] = []
        self._headings: list[str] = []
        self._in_table = False
        self._in_row = False
        self._in_cell = False
        self._is_header = False
        self._current_table: dict[str, Any] = {}
        self._current_row: list[str] = []
        self._current_cell_text = ""
        self._in_heading = False
        self._heading_text = ""
        self._heading_tag = ""
        self._meta: dict[str, str] = {}
        self._in_title = False
        self._title_text = ""
        self._in_li = False
        self._li_text = ""
        self._li_has_child_element = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = True
            self._title_text = ""
        elif tag in ("h1", "h2", "h3", "h4"):
            self._in_heading = True
            self._heading_text = ""
            self._heading_tag = tag
        elif tag == "li" and not self._in_table:
            self._in_li = True
            self._li_text = ""
            self._li_has_child_element = False
        elif self._in_li and tag in ("a", "ul", "ol"):
            self._li_has_child_element = True
        elif tag == "table":
            self._in_table = True
            self._current_table = {"heading": "", "headers": [], "rows": []}
            if self._headings:
                self._current_table["heading"] = self._headings[-1]
        elif tag == "tr" and self._in_table:
            self._in_row = True
            self._current_row = []
        elif tag == "th" and self._in_row:
            self._in_cell = True
            self._is_header = True
            self._current_cell_text = ""
        elif tag == "td" and self._in_row:
            self._in_cell = True
            self._is_header = False
            self._current_cell_text = ""

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
            self._meta["title"] = self._title_text.strip()
        elif tag == "li" and self._in_li:
            self._in_li = False
            text = self._li_text.strip()
            if text and not self._li_has_child_element and text.endswith(":") and len(text) < 80:
                self._headings.append(text.rstrip(":"))
        elif tag in ("h1", "h2", "h3", "h4") and self._in_heading:
            self._in_heading = False
            text = self._heading_text.strip()
            if text:
                self._headings.append(text)
        elif tag == "table" and self._in_table:
            self._in_table = False
            if self._current_table.get("headers") or self._current_table.get("rows"):
                self._tables.append(self._current_table)
            self._current_table = {}
        elif tag == "tr" and self._in_row:
            self._in_row = False
            if self._current_row:
                if all(not c for c in self._current_row):
                    pass
                elif not self._current_table.get("headers"):
                    self._current_table["headers"] = self._current_row
                else:
                    self._current_table.setdefault("rows", []).append(self._current_row)
        elif tag in ("th", "td") and self._in_cell:
            self._in_cell = False
            self._current_row.append(self._current_cell_text.strip())

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_text += data
        if self._in_heading:
            self._heading_text += data
        if self._in_li:
            self._li_text += data
        if self._in_cell:
            self._current_cell_text += data

    def get_results(self) -> dict[str, Any]:
        return {
            "meta": self._meta,
            "headings": self._headings,
            "tables": self._tables,
        }


def _extract_embedded_json(html: str) -> dict[str, Any] | None:
    """Extract the `const data={...}` embedded JSON from Admin/ctlg-style reports."""
    match = re.search(r"const\s+data\s*=\s*(\{.+?\})\s*(?:;|\n|class\s)", html, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        raw = match.group(1)
        end_idx = _find_json_end(raw)
        if end_idx > 0:
            try:
                return json.loads(raw[:end_idx])
            except json.JSONDecodeError:
                pass
    return None


def _find_json_end(s: str) -> int:
    """Find the index of the closing brace that matches the opening brace."""
    depth = 0
    in_string = False
    escape = False
    for i, ch in enumerate(s):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i + 1
    return -1


def _summarize_json_data(data: dict[str, Any]) -> str:
    """Summarize embedded JSON data into readable text."""
    lines: list[str] = []

    report_type = data.get("type", "unknown")
    lines.append(f"Report Type: {report_type}")

    props = data.get("properties", {})
    if props:
        lines.append("\n## Report Properties")
        for key in ("description", "server_description", "report_start1", "report_end1",
                     "report_start2", "report_end2", "server_name", "server_version"):
            val = props.get(key)
            if val:
                lines.append(f"- {key}: {val}")

    datasets = data.get("datasets", {})
    if datasets:
        lines.append(f"\n## Datasets ({len(datasets)} total)")
        for i, (name, rows) in enumerate(datasets.items()):
            if i >= _MAX_JSON_DATASETS:
                lines.append(f"... and {len(datasets) - i} more datasets")
                break
            if isinstance(rows, list):
                lines.append(f"\n### {name} ({len(rows)} rows)")
                if rows and isinstance(rows[0], dict):
                    headers = list(rows[0].keys())
                    lines.append("| " + " | ".join(headers) + " |")
                    lines.append("| " + " | ".join("---" for _ in headers) + " |")
                    for row in rows[:_MAX_DATASET_ROWS]:
                        vals = [str(row.get(h, "")) for h in headers]
                        lines.append("| " + " | ".join(vals) + " |")
                    if len(rows) > _MAX_DATASET_ROWS:
                        lines.append(f"... ({len(rows) - _MAX_DATASET_ROWS} more rows)")
            elif isinstance(rows, dict):
                lines.append(f"\n### {name}")
                for k, v in list(rows.items())[:20]:
                    lines.append(f"- {k}: {v}")

    sections = data.get("sections", [])
    if sections:
        lines.append(f"\n## Sections ({len(sections)} total)")
        _summarize_sections(sections, lines, depth=0)

    return "\n".join(lines)


def _summarize_sections(sections: list[dict], lines: list[str], depth: int) -> None:
    """Recursively summarize report sections."""
    prefix = "  " * depth
    for section in sections[:20]:
        name = section.get("header", section.get("name", "unnamed"))
        lines.append(f"{prefix}- {name}")
        data_list = section.get("data", [])
        if isinstance(data_list, list) and data_list and isinstance(data_list[0], dict):
            headers = list(data_list[0].keys())[:10]
            lines.append(f"{prefix}  Columns: {', '.join(headers)}")
            lines.append(f"{prefix}  Rows: {len(data_list)}")
        nested = section.get("sections", [])
        if nested:
            _summarize_sections(nested, lines, depth + 1)


def _tables_to_text(tables: list[dict[str, Any]]) -> str:
    """Convert extracted HTML tables to markdown-style text."""
    lines: list[str] = []
    for table in tables:
        heading = table.get("heading", "")
        if heading:
            lines.append(f"\n## {heading}")

        headers = table.get("headers", [])
        rows = table.get("rows", [])

        if not headers and not rows:
            continue

        if headers:
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("| " + " | ".join("---" for _ in headers) + " |")

        for row in rows[:_MAX_TABLE_ROWS]:
            padded = row + [""] * max(0, len(headers) - len(row))
            lines.append("| " + " | ".join(padded[:len(headers)] if headers else padded) + " |")

        if len(rows) > _MAX_TABLE_ROWS:
            lines.append(f"... ({len(rows) - _MAX_TABLE_ROWS} more rows)")

    return "\n".join(lines)


def parse_html_report(html_content: str, filename: str = "") -> str:
    """
    Parse an HTML report and return a plain-text summary for LLM context.

    Handles both PGAWR-style (HTML tables) and Admin/ctlg-style (embedded JSON).
    """
    parts: list[str] = []

    if filename:
        parts.append(f"# Report: {filename}")

    json_data = _extract_embedded_json(html_content)
    if json_data:
        parts.append(_summarize_json_data(json_data))
    
    extractor = _TableExtractor()
    try:
        extractor.feed(html_content)
    except Exception as e:
        logger.warning("HTML parsing error for %s: %s", filename, e)

    results = extractor.get_results()

    meta = results.get("meta", {})
    if meta.get("title"):
        parts.append(f"Title: {meta['title']}")

    tables = results.get("tables", [])
    if tables:
        table_text = _tables_to_text(tables)
        if table_text.strip():
            if json_data:
                parts.append("\n## HTML Tables")
            parts.append(table_text)

    if not parts or (len(parts) == 1 and parts[0].startswith("# Report:")):
        parts.append("(Could not extract structured data from this report)")

    return "\n\n".join(parts)
