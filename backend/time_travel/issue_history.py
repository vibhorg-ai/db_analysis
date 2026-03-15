"""Tracks detected issues over time."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any


@dataclass
class Issue:
    id: str
    timestamp: float
    severity: str
    title: str
    description: str
    source: str = ""
    category: str = "other"  # performance, locks, schema, configuration, maintenance, security, other
    resolved: bool = False
    resolved_at: float | None = None
    connection_id: str = ""


class IssueHistory:
    def __init__(self) -> None:
        self._issues: list[Issue] = []
        self._lock = threading.Lock()

    def record(
        self,
        severity: str,
        title: str,
        description: str,
        source: str = "",
        category: str = "other",
        connection_id: str = "",
    ) -> Issue:
        """Record a new issue."""
        issue = Issue(
            id=str(uuid.uuid4()),
            timestamp=time.time(),
            severity=severity.lower(),
            title=title,
            description=description,
            source=source,
            category=category,
            connection_id=connection_id,
        )
        with self._lock:
            self._issues.append(issue)
            return issue

    def resolve(self, issue_id: str) -> bool:
        """Mark an issue as resolved. Returns True if found and resolved."""
        with self._lock:
            for issue in self._issues:
                if issue.id == issue_id:
                    issue.resolved = True
                    issue.resolved_at = time.time()
                    return True
            return False

    def get_open_issues(self) -> list[Issue]:
        """Return unresolved issues."""
        with self._lock:
            return [i for i in self._issues if not i.resolved]

    def get_all_issues(self, limit: int = 200) -> list[Issue]:
        """Return all issues (most recent first), capped by limit."""
        with self._lock:
            return list(self._issues[-limit:][::-1])

    def get_issues_by_severity(self, severity: str) -> list[Issue]:
        """Return issues matching the given severity."""
        with self._lock:
            return [i for i in self._issues if i.severity == severity.lower()]

    def get_issues_by_category(self, category: str) -> list[Issue]:
        """Return issues matching the given category."""
        with self._lock:
            return [i for i in self._issues if i.category == category.lower()]

    def get_issues_since(self, since_timestamp: float) -> list[Issue]:
        """Return issues detected since the given timestamp."""
        with self._lock:
            return [i for i in self._issues if i.timestamp > since_timestamp]


_instance: IssueHistory | None = None


def get_issue_history() -> IssueHistory:
    """Return singleton IssueHistory instance."""
    global _instance
    if _instance is None:
        _instance = IssueHistory()
    return _instance
