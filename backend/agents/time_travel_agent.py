"""
Time-travel agent — analyzes historical database state.
"""

from __future__ import annotations

from typing import Any


class TimeTravelAgent:
    """Analyzes historical database state to detect schema evolution, performance changes, issue history."""

    def __init__(self, llm: Any, prompt: str) -> None:
        self.llm = llm
        self.prompt = prompt

    async def run(self, context: dict) -> dict:
        """Gather historical data from all time-travel stores, send to LLM, return analysis."""
        from backend.core.config import get_settings
        from backend.core.prompt_trim import CHARS_PER_TOKEN, trim_context_for_llm
        from backend.time_travel import (
            get_schema_history,
            get_query_history,
            get_performance_history,
            get_issue_history,
        )

        schema_h = get_schema_history()
        query_h = get_query_history()
        perf_h = get_performance_history()
        issue_h = get_issue_history()

        schema_changes = schema_h.get_changes_since(0.0)
        schema_history = schema_h.get_history(limit=20)

        perf_trend = perf_h.get_trend(hours=24)
        perf_history = perf_h.get_history(limit=50)

        slow_queries = query_h.get_slow_queries(threshold_ms=1000, limit=30)
        recent_queries = query_h.get_history(limit=50)

        open_issues = issue_h.get_open_issues()
        recent_issues = issue_h.get_all_issues(limit=50)

        historical_summary: dict[str, Any] = {
            "schema_changes": [
                {
                    "timestamp": c["timestamp"],
                    "changes": c["changes"],
                }
                for c in schema_changes
            ],
            "schema_snapshots_count": len(schema_history),
            "performance_trend": perf_trend,
            "performance_snapshots_count": len(perf_history),
            "slow_queries_sample": [
                {
                    "timestamp": r.timestamp,
                    "query": r.query[:500] + ("..." if len(r.query) > 500 else ""),
                    "duration_ms": r.duration_ms,
                    "source": r.source,
                }
                for r in slow_queries
            ],
            "recent_queries_count": len(recent_queries),
            "open_issues_count": len(open_issues),
            "open_issues": [
                {
                    "id": i.id,
                    "timestamp": i.timestamp,
                    "severity": i.severity,
                    "title": i.title,
                    "description": i.description[:500] + ("..." if len(i.description) > 500 else ""),
                    "source": i.source,
                }
                for i in open_issues
            ],
            "recent_issues": [
                {
                    "id": i.id,
                    "timestamp": i.timestamp,
                    "severity": i.severity,
                    "title": i.title,
                    "source": i.source,
                    "resolved": i.resolved,
                }
                for i in recent_issues[-50:]
            ],
        }

        context_with_history = dict(context)
        context_with_history["historical_summary"] = historical_summary

        settings = get_settings()
        max_chars = settings.llm_max_context_tokens * CHARS_PER_TOKEN
        context_str = trim_context_for_llm(
            context_with_history, max_chars, reserved_chars=len(self.prompt) + 200
        )
        prompt_text = f"{self.prompt}\n\n# INPUT DATA (including historical summaries)\n\n{context_str}"
        raw_response = await self.llm.generate(prompt_text)

        return {
            "raw_response": raw_response,
            "historical_summary": historical_summary,
        }
