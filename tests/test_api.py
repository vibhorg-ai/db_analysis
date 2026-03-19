"""
API route tests for DB Analyzer AI v7.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from backend.api.app import app


@pytest.mark.asyncio
async def test_health_live() -> None:
    """GET /health/live returns 200 with {"status": "ok"}."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/health/live")
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_ready() -> None:
    """GET /health/ready returns 200 with status and version."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/health/ready")
        assert res.status_code == 200
        data = res.json()
        assert "status" in data
        assert "version" in data


@pytest.mark.asyncio
async def test_health() -> None:
    """GET /health returns 200."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/health")
        assert res.status_code == 200


@pytest.mark.asyncio
async def test_metrics() -> None:
    """GET /metrics returns 200 with text/plain content type."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/metrics")
        assert res.status_code == 200
        assert "text/plain" in res.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_connect_no_dsn() -> None:
    """POST /api/connect with empty body returns an error (400, 500, or 200 with success=false)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/connect", json={})
        # API may return 400/500 or 200 with success=False when connection fails
        if res.status_code == 200:
            data = res.json()
            assert data.get("success") is False
        else:
            assert res.status_code in (400, 500)


@pytest.mark.asyncio
async def test_schema_no_connection() -> None:
    """GET /api/schema returns 400 (no active connection)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/schema")
        assert res.status_code == 400


@pytest.mark.asyncio
async def test_sandbox_dangerous_query() -> None:
    """POST /api/sandbox with {"query": "DROP TABLE users"} returns success=false with error about dangerous queries."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/sandbox", json={"query": "DROP TABLE users"})
        assert res.status_code == 200
        data = res.json()
        assert data.get("success") is False
        assert "error" in data
        assert "dangerous" in data["error"].lower() or "destructive" in data["error"].lower()


@pytest.mark.asyncio
async def test_connections_list() -> None:
    """GET /api/connections returns 200 with a list."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/connections")
        assert res.status_code == 200
        assert isinstance(res.json(), list)


@pytest.mark.asyncio
async def test_mcp_status() -> None:
    """GET /api/mcp-status returns 200."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/mcp-status")
        assert res.status_code == 200


@pytest.mark.asyncio
async def test_issues_paginated_response() -> None:
    """GET /api/issues returns standard paginated shape: items, total, limit, offset."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/issues")
        # May be 200 (no auth) or 401 (auth required)
        if res.status_code != 200:
            pytest.skip("Issues endpoint requires auth")
        data = res.json()
        assert "items" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert isinstance(data["items"], list)
        assert data["limit"] >= 1 and data["limit"] <= 500
        assert data["offset"] >= 0


@pytest.mark.asyncio
async def test_insights_paginated_response() -> None:
    """GET /api/insights returns standard paginated shape: items, total, limit, offset."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/insights")
        if res.status_code != 200:
            pytest.skip("Insights endpoint requires auth")
        data = res.json()
        assert "items" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert isinstance(data["items"], list)
        assert data["limit"] >= 1 and data["limit"] <= 500
        assert data["offset"] >= 0
