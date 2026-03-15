# Connector layer: base protocol, Postgres, Couchbase, MCP adapter

from .base import ConnectionResult, ConnectorProtocol, is_dangerous_query
from .postgres_connector import PostgresConnector

try:
    from .couchbase_connector import CouchbaseConnector
except ImportError:
    CouchbaseConnector = None  # type: ignore[misc, assignment]

__all__ = [
    "ConnectionResult",
    "ConnectorProtocol",
    "is_dangerous_query",
    "PostgresConnector",
    "CouchbaseConnector",
]
