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
    port: int | None = Field(default=None, ge=1, le=65535)
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
    query: str = Field(..., min_length=1)
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


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    context_summary: dict[str, Any] = {}


# --- Index recommendations ---


class IndexRecommendationsResponse(BaseModel):
    recommendations: list[dict[str, Any]] = []


# --- Sandbox ---


class SandboxQueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
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


# --- Insights (Autonomous Advisor) ---


class InsightResponse(BaseModel):
    id: str
    timestamp: float
    category: str = "performance"
    title: str = ""
    description: str = ""
    recommendation: str = ""
    suggested_sql: str | None = None
    impact: str = "medium"
    confidence: float = 0.0
    risk: str = "low"
    connection_id: str = ""
    source: str = "advisor"
    dismissed: bool = False
    dismissed_at: float | None = None


class InsightDismissResponse(BaseModel):
    success: bool
    message: str


# --- Simulation Engine ---


class SimulateRequest(BaseModel):
    change_type: str  # add_index, remove_index, drop_column, partition_table, query_comparison, growth, dependency_impact
    connection_id: str | None = None
    table: str = Field(default="", max_length=512)
    column: str = Field(default="", max_length=512)
    columns: list[str] = []
    index_name: str = Field(default="", max_length=512)
    partition_column: str = Field(default="", max_length=512)
    target_rows: int = Field(default=0, ge=0, le=100_000_000_000)
    original_query: str = ""
    optimized_query: str = ""


class SimulateResponse(BaseModel):
    id: str
    simulation_type: str
    input_description: str
    result: dict[str, Any] = {}
    connection_id: str = ""
    timestamp: float = 0.0


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
    connected: bool = False
