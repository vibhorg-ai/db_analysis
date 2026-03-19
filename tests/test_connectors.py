"""
Connector layer tests for DB Analyzer AI v7.
"""

from unittest.mock import patch

import pytest

from backend.connectors import PostgresConnector, is_dangerous_query
from backend.connectors.base import ConnectionResult
from backend.core.db_registry import get_registry
from backend.core.schema_cache import SchemaCache


class TestIsDangerousQuery:
    """Tests for is_dangerous_query."""

    def test_dangerous_drop_table(self):
        assert is_dangerous_query("DROP TABLE users") is True

    def test_dangerous_delete_from(self):
        assert is_dangerous_query("DELETE FROM users WHERE id = 1") is True

    def test_dangerous_truncate(self):
        assert is_dangerous_query("TRUNCATE TABLE users") is True

    def test_dangerous_alter_table(self):
        assert is_dangerous_query("ALTER TABLE users ADD COLUMN foo INT") is True

    def test_safe_select(self):
        assert is_dangerous_query("SELECT * FROM users") is False

    def test_safe_explain(self):
        assert is_dangerous_query("EXPLAIN SELECT * FROM users") is False

    def test_dangerous_prepare_execute(self):
        assert is_dangerous_query("PREPARE stmt AS INSERT INTO t VALUES (1)") is True
        assert is_dangerous_query("EXECUTE stmt") is True

    def test_dangerous_select_into(self):
        assert is_dangerous_query("SELECT * INTO new_table FROM users") is True


class TestConnectionResult:
    """Tests for ConnectionResult."""

    def test_connection_result_success(self):
        result = ConnectionResult(success=True, message="Connected", details={"version": "15.1"})
        assert result.success is True
        assert result.message == "Connected"
        assert result.details == {"version": "15.1"}

    def test_connection_result_failure(self):
        result = ConnectionResult(success=False, message="Connection refused")
        assert result.success is False
        assert result.message == "Connection refused"
        assert result.details == {}


class TestSchemaCache:
    """Tests for SchemaCache."""

    def test_schema_cache_get_set(self):
        cache = SchemaCache()
        dsn = "postgresql://user:pass@localhost/db"
        tables = [{"table_name": "users", "columns": []}]
        cache.set(dsn, tables)
        assert cache.get(dsn) == tables

    def test_schema_cache_get_missing(self):
        cache = SchemaCache()
        assert cache.get("postgresql://nonexistent/db") is None

    def test_schema_cache_get_set_ttl_expiry(self):
        """Test that TTL expiry returns None (mock time)."""
        cache = SchemaCache()
        dsn = "postgresql://user:pass@localhost/db"
        tables = [{"table_name": "users", "columns": []}]

        with patch("backend.core.schema_cache.get_settings") as mock_settings:
            mock_settings.return_value.schema_cache_ttl_seconds = 10
            with patch("backend.core.schema_cache.time") as mock_time:
                # set uses 100, first get uses 105 (5s elapsed, cache hit), second get uses 111 (11s elapsed, expired)
                mock_time.monotonic.side_effect = [100.0, 105.0, 111.0]
                cache.set(dsn, tables)
                assert cache.get(dsn) == tables
                assert cache.get(dsn) is None

    def test_schema_cache_invalidate(self):
        cache = SchemaCache()
        dsn = "postgresql://user:pass@localhost/db"
        tables = [{"table_name": "users", "columns": []}]
        cache.set(dsn, tables)
        assert cache.get(dsn) == tables
        cache.invalidate(dsn)
        assert cache.get(dsn) is None


class TestDBRegistry:
    """Tests for DBRegistry."""

    def test_db_registry_list_connections(self):
        registry = get_registry()
        connections = registry.list_connections()
        assert isinstance(connections, list)


class TestPostgresConnector:
    """Tests for PostgresConnector."""

    def test_postgres_connector_init(self):
        """PostgresConnector can be instantiated with a DSN without connecting."""
        connector = PostgresConnector(dsn="postgresql://user:pass@localhost:5432/testdb")
        assert connector._dsn == "postgresql://user:pass@localhost:5432/testdb"
        assert connector._conn is None
