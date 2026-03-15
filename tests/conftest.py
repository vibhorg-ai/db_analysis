"""
Pytest fixtures for DB Analyzer AI v5.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest
from httpx import ASGITransport

from backend.connectors.base import ConnectionResult
from backend.core.config import Settings, get_settings
from backend.core.db_registry import get_registry
from backend.core.schema_cache import SchemaCache
from backend.graph.knowledge_graph import KnowledgeGraph

# Import app after other imports to avoid circular issues
from backend.api.app import app


@pytest.fixture
def settings() -> Settings:
    """Return a Settings instance from backend.core.config."""
    return get_settings()


@pytest.fixture
def schema_cache() -> SchemaCache:
    """Return a fresh SchemaCache; invalidate_all called in cleanup."""
    cache = SchemaCache()
    yield cache
    cache.invalidate_all()


@pytest.fixture
def db_registry():
    """Return the registry from backend.core.db_registry.get_registry."""
    return get_registry()


@pytest.fixture
def knowledge_graph() -> KnowledgeGraph:
    """Return a fresh KnowledgeGraph instance."""
    return KnowledgeGraph()


@pytest.fixture
def mock_connector():
    """Return a simple mock postgres connector with predefined responses."""
    mock = AsyncMock()

    async def _connect():
        return ConnectionResult(success=True, message="mock connected")

    async def _disconnect():
        return None

    async def _health_check():
        return {"status": "ok"}

    async def _execute_read_only(query, *args, **kwargs):
        return [{"id": 1, "name": "test"}]

    sample_schema = [
        {
            "table_name": "users",
            "name": "users",
            "schema": "public",
            "row_count": 0,
            "columns": [
                {"name": "id", "data_type": "integer", "is_nullable": False},
                {"name": "name", "data_type": "text", "is_nullable": False},
                {"name": "org_id", "data_type": "integer", "is_nullable": True},
            ],
            "primary_key": "id",
            "foreign_keys": [
                {
                    "column": "org_id",
                    "target_table": "organizations",
                    "ref_column": "id",
                    "relationship_type": "one_to_many",
                }
            ],
        },
        {
            "table_name": "organizations",
            "name": "organizations",
            "schema": "public",
            "row_count": 0,
            "columns": [
                {"name": "id", "data_type": "integer", "is_nullable": False},
                {"name": "name", "data_type": "text", "is_nullable": False},
                {"name": "created_at", "data_type": "timestamp", "is_nullable": True},
            ],
            "primary_key": "id",
            "foreign_keys": [],
        },
    ]

    async def _fetch_schema_metadata(timeout: float = 30.0):
        return sample_schema

    mock.connect = _connect
    mock.disconnect = _disconnect
    mock.health_check = _health_check
    mock.execute_read_only = _execute_read_only
    mock.fetch_schema_metadata = _fetch_schema_metadata
    return mock


@pytest.fixture
async def test_client():
    """Return an httpx.AsyncClient bound to the FastAPI app."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        yield client
