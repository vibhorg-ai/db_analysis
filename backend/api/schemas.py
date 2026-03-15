"""
Pydantic request/response models for DB Analyzer AI v5 API.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# --- Connection ---


class ConnectDBRequest(BaseModel):
    engine: str = "postgres"
    connection_id: str | None = None
    dsn: str | None = None
    host: str | None = None
    port: int | None = None
    database: str | None = None
    user: str | None = None
    password: str | None = None
    connection_string: str | None = None
    bucket: str | None = None
    username: str | None = None


class ConnectDBResponse(BaseModel):
    success: bool
    message: str
    connection_id: str | None = None
    details: dict[str, Any] = {}


# --- Analysis ---


class AnalyzeQueryRequest(BaseModel):
    query: str
    connection_id: str | None = None
    mode: str = "full"  # "full", "query_only", "index_only"


class AnalyzeQueryResponse(BaseModel):
    run_id: str | None = None
    mode: str = "full"
    results: dict[str, Any] = {}
    timing: dict[str, float] = {}


# --- Schema ---


class SchemaResponse(BaseModel):
    tables: list[dict[str, Any]] = []
    connection_id: str | None = None


# --- Health ---


class DBHealthResponse(BaseModel):
    score: int = 0
    status: str = "unknown"
    metrics: list[dict[str, Any]] = []
    alerts: list[dict[str, Any]] = []


# --- Chat ---


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    context_summary: dict[str, Any] = {}


# --- Index recommendations ---


class IndexRecommendationsResponse(BaseModel):
    recommendations: list[dict[str, Any]] = []


# --- Sandbox ---


class SandboxQueryRequest(BaseModel):
    query: str
    connection_id: str | None = None


class SandboxQueryResponse(BaseModel):
    success: bool
    rows: list[dict[str, Any]] = []
    row_count: int = 0
    error: str | None = None


# --- MCP status ---


class MCPStatusResponse(BaseModel):
    postgres: dict[str, Any] = {}
    couchbase: dict[str, Any] = {}


# --- Issues ---


class IssueResponse(BaseModel):
    id: str
    timestamp: float
    severity: str
    title: str
    description: str
    source: str = ""
    category: str = "other"
    resolved: bool = False
    resolved_at: float | None = None
    connection_id: str = ""


class IssueResolveResponse(BaseModel):
    success: bool
    message: str


# --- Multi-DB Health ---


class AllDBHealthResponse(BaseModel):
    connections: dict[str, DBHealthResponse] = {}


# --- Connection registry ---


class AddConnectionRequest(BaseModel):
    name: str
    engine: str = "postgres"
    default: bool = False
    host: str | None = None
    port: int | None = None
    database: str | None = None
    user: str | None = None
    password: str | None = None
    connection_string: str | None = None
    bucket: str | None = None
    username: str | None = None


class DBConnectionItem(BaseModel):
    id: str
    name: str
    engine: str
    default: bool = False
