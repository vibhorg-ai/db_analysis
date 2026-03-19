"""
Chat session context manager for DB Analyzer AI v7.

Accumulates session context across the conversation:
- Conversation history (messages)
- Uploaded report summaries
- Schema metadata from active connection
- Health metrics snapshot
- Previous analysis results
- Connection info

Assembles everything into a system prompt for the LLM.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from backend.core.prompt_trim import CHARS_PER_TOKEN, estimate_tokens

logger = logging.getLogger(__name__)

SESSION_TTL_SECONDS = 3600  # 1 hour
MAX_REPORT_CONTEXT_CHARS = 40_000
MAX_SCHEMA_CONTEXT_CHARS = 20_000
MAX_HISTORY_MESSAGES = 50


@dataclass
class ChatSession:
    """Holds all context for a single chat session."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    messages: list[dict[str, str]] = field(default_factory=list)
    reports: list[dict[str, str]] = field(default_factory=list)
    schema_context: str | None = None
    health_context: str | None = None
    analysis_results: list[dict[str, Any]] = field(default_factory=list)
    connection_info: dict[str, Any] | None = None
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.last_active = time.time()

    def is_expired(self) -> bool:
        return (time.time() - self.last_active) > SESSION_TTL_SECONDS

    def add_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
        if len(self.messages) > MAX_HISTORY_MESSAGES * 2:
            self.messages = self.messages[-MAX_HISTORY_MESSAGES:]
        self.touch()

    def add_report(self, filename: str, parsed_content: str) -> None:
        if len(parsed_content) > MAX_REPORT_CONTEXT_CHARS:
            parsed_content = parsed_content[:MAX_REPORT_CONTEXT_CHARS] + "\n...(truncated)"
        self.reports.append({"filename": filename, "content": parsed_content})
        self.touch()

    def set_schema(self, schema_text: str) -> None:
        if len(schema_text) > MAX_SCHEMA_CONTEXT_CHARS:
            schema_text = schema_text[:MAX_SCHEMA_CONTEXT_CHARS] + "\n...(truncated)"
        self.schema_context = schema_text
        self.touch()

    def set_health(self, health_text: str) -> None:
        self.health_context = health_text
        self.touch()

    def add_analysis_result(self, result: dict[str, Any]) -> None:
        self.analysis_results.append(result)
        if len(self.analysis_results) > 10:
            self.analysis_results = self.analysis_results[-10:]
        self.touch()

    def set_connection_info(self, info: dict[str, Any]) -> None:
        self.connection_info = info
        self.touch()

    def build_system_prompt(self, max_tokens: int = 20000) -> str:
        """Assemble all accumulated context into a system prompt."""
        sections: list[str] = []
        sections.append(
            "You are DB Analyzer AI, an expert PostgreSQL and Couchbase assistant. "
            "Be concise, technical, and specific. Use context below.\n\n"
            "RULES:\n"
            "- Markdown always. SQL/N1QL in ```sql blocks. `inline code` for identifiers.\n"
            "- Check Active Connection for engine. PostgreSQL=SQL, Couchbase=N1QL with backticks. Never mix.\n"
            "- Only reference tables/columns that exist in the schema context. No placeholders.\n"
            "- If no schema loaded, tell user to connect a database first."
        )

        if self.connection_info:
            info = self.connection_info
            engine = info.get("engine", "unknown")
            safe_info = {k: v for k, v in info.items() if k not in ("password", "dsn", "connector")}
            sections.append(
                f"\n## Active Connection\n"
                f"**ENGINE: {engine.upper()}** — ALL queries MUST be valid {engine.upper()} syntax.\n"
                f"{json.dumps(safe_info, default=str)}"
            )

        if self.schema_context:
            sections.append(f"\n## Database Schema\n{self.schema_context}")

        if self.health_context:
            sections.append(f"\n## Health Metrics\n{self.health_context}")

        if len(self.reports) >= 2:
            groups = self._detect_report_groups()
            if groups:
                comparison_lines = ["\n## Report Comparison Instructions"]
                comparison_lines.append(
                    "The following reports appear to be from the same source at different timestamps. "
                    "When the user asks about these reports, highlight key differences in metrics, "
                    "thresholds, alerts, and performance indicators between them."
                )
                for group_name, filenames in groups.items():
                    comparison_lines.append(f"\nGroup '{group_name}': {', '.join(filenames)}")
                sections.append("\n".join(comparison_lines))

        per_report_limit = MAX_REPORT_CONTEXT_CHARS
        if len(self.reports) >= 2:
            per_report_limit = MAX_REPORT_CONTEXT_CHARS // len(self.reports)

        for report in self.reports:
            content = report["content"]
            if len(content) > per_report_limit:
                content = content[:per_report_limit] + "\n...(report truncated for multi-report context)"
            sections.append(f"\n## Report: {report['filename']}\n{content}")

        if self.analysis_results:
            latest = self.analysis_results[-3:]
            for result in latest:
                summary = json.dumps(result, default=str)
                if len(summary) > 5000:
                    summary = summary[:5000] + "...(truncated)"
                sections.append(f"\n## Previous Analysis Result\n{summary}")

        full = "\n".join(sections)

        max_chars = max_tokens * CHARS_PER_TOKEN
        if len(full) > max_chars:
            full = full[:max_chars] + "\n...(context truncated to fit token limit)"

        return full

    def get_messages_for_llm(self) -> list[dict[str, str]]:
        """Return message list with system prompt prepended."""
        system_prompt = self.build_system_prompt()
        result: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        result.extend(self.messages)
        return result

    def context_summary(self) -> dict[str, Any]:
        """Return a summary of what context is loaded (for the frontend)."""
        return {
            "session_id": self.session_id,
            "message_count": len(self.messages),
            "reports_loaded": [r["filename"] for r in self.reports],
            "has_schema": self.schema_context is not None,
            "has_health": self.health_context is not None,
            "analysis_count": len(self.analysis_results),
            "has_connection": self.connection_info is not None,
        }

    def _detect_report_groups(self) -> dict[str, list[str]]:
        """Group reports by normalized name pattern for comparison."""
        groups: dict[str, list[str]] = {}
        for report in self.reports:
            filename = report["filename"]
            normalized = re.sub(r'\d{10,}|\d{4}[-_]\d{2}[-_]\d{2}|\d{12,}', 'TIMESTAMP', filename)
            normalized = re.sub(r'_\d+_\d+_', '_ID_', normalized)
            normalized = re.sub(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', 'IP', normalized)
            if normalized not in groups:
                groups[normalized] = []
            groups[normalized].append(filename)
        return {k: v for k, v in groups.items() if len(v) >= 2}


class ChatSessionStore:
    """Thread-safe in-memory store for chat sessions with TTL cleanup."""

    MAX_SESSIONS = 500

    def __init__(self) -> None:
        self._sessions: dict[str, ChatSession] = {}
        self._lock = threading.Lock()

    def get_or_create(self, session_id: str | None = None) -> ChatSession:
        with self._lock:
            if session_id and session_id in self._sessions:
                session = self._sessions[session_id]
                if not session.is_expired():
                    session.touch()
                    return session
                del self._sessions[session_id]

            if len(self._sessions) >= self.MAX_SESSIONS:
                oldest_id = min(self._sessions, key=lambda k: self._sessions[k].last_active)
                del self._sessions[oldest_id]

            session = ChatSession(session_id=session_id or str(uuid.uuid4()))
            self._sessions[session.session_id] = session
            return session

    def get(self, session_id: str) -> ChatSession | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session and not session.is_expired():
                return session
            if session:
                del self._sessions[session_id]
            return None

    def cleanup_expired(self) -> int:
        """Remove expired sessions. Returns count of removed sessions."""
        with self._lock:
            expired = [sid for sid, s in self._sessions.items() if s.is_expired()]
            for sid in expired:
                del self._sessions[sid]
            return len(expired)


_store: ChatSessionStore | None = None
_store_lock = threading.Lock()


def get_session_store() -> ChatSessionStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = ChatSessionStore()
        return _store
