"""
Context/prompt trimming utilities for LLM token limits.
"""

from __future__ import annotations

import json
from typing import Any

CHARS_PER_TOKEN = 4


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


def _summarize_report_contents(report_contents: list[Any]) -> list[dict[str, Any]]:
    """Replace full report content with summaries (id, type, content_length, content_preview of 2000 chars)."""
    summaries: list[dict[str, Any]] = []
    preview_len = 2000
    for item in report_contents:
        if isinstance(item, dict):
            content = item.get("content", "")
            if isinstance(content, str):
                content_len = len(content)
                content_preview = content[:preview_len] + ("..." if len(content) > preview_len else "")
            else:
                content_str = str(content)
                content_len = len(content_str)
                content_preview = content_str[:preview_len] + ("..." if len(content_str) > preview_len else "")
            summaries.append({
                "id": item.get("id"),
                "type": item.get("type"),
                "content_length": content_len,
                "content_preview": content_preview,
            })
        else:
            summaries.append({"raw": str(item)[:500]})
    return summaries


def trim_context_for_llm(
    context: dict[str, Any],
    max_total_chars: int,
    reserved_chars: int = 500,
) -> str:
    """Build a context string safe for LLM context window."""
    budget = max_total_chars - reserved_chars
    trimmed: dict[str, Any] = {}

    for key, value in context.items():
        if key == "report_contents" and isinstance(value, list):
            trimmed[key] = _summarize_report_contents(value)
        elif key == "schema_metadata":
            if isinstance(value, str) and len(value) > 25000:
                trimmed[key] = value[:25000] + "...[truncated]"
            else:
                trimmed[key] = _truncate_value(value, 25000)
        else:
            trimmed[key] = _truncate_value(value, 8000)

    result = json.dumps(trimmed, default=str)
    if len(result) > budget:
        result = result[:budget] + "...[truncated]"
    return result
