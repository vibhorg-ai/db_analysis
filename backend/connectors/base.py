"""
Base protocol and types for database connectors (v5).
All DB access goes through this layer. MCP or direct implementations.
"""

from typing import Any, Protocol, runtime_checkable

_DANGEROUS_KEYWORDS = frozenset({
    "DROP", "DELETE", "TRUNCATE", "ALTER", "CREATE", "INSERT", "UPDATE",
    "REPLACE", "COPY", "GRANT", "REVOKE", "CALL", "REINDEX", "MERGE",
    "PREPARE", "EXECUTE", "INTO",  # PREPARE/EXECUTE can run arbitrary SQL; SELECT INTO writes
})


def is_dangerous_query(text: str) -> bool:
    """True if the query appears to contain a dangerous DDL/DML keyword."""
    import re
    cleaned = re.sub(r"--[^\n]*", " ", text)
    cleaned = re.sub(r"/\*.*?\*/", " ", cleaned, flags=re.DOTALL)
    for statement in cleaned.split(";"):
        upper = statement.strip().upper()
        if not upper:
            continue
        padded = f" {upper} "
        for kw in _DANGEROUS_KEYWORDS:
            if upper.startswith(kw) or f" {kw} " in padded:
                return True
    return False


@runtime_checkable
class ConnectorProtocol(Protocol):
    """Contract for database connectors."""

    async def connect(self) -> "ConnectionResult":
        """Establish connection."""
        ...

    async def disconnect(self) -> None:
        """Close connection and release resources."""
        ...

    async def health_check(self) -> dict[str, Any]:
        """Return connection health and basic stats."""
        ...

    async def execute_read_only(self, query: str, *args: Any, **kwargs: Any) -> Any:
        """Execute read-only statement. Raises if query is dangerous."""
        ...


class ConnectionResult:
    """Result of a connection attempt."""

    def __init__(self, success: bool, message: str = "", details: dict[str, Any] | None = None):
        self.success = success
        self.message = message
        self.details = details or {}
