"""
API route handlers for DB Analyzer AI v5.
Connection management, schema, analysis pipeline, health, chat, sandbox.
"""

from __future__ import annotations

import logging
import re
import threading
import uuid
from typing import Any
from urllib.parse import quote_plus

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from backend.core.auth import UserContext, require_permission
from backend.api.schemas import (
    AddConnectionRequest,
    AllDBHealthResponse,
    AnalyzeQueryRequest,
    AnalyzeQueryResponse,
    ChatResponse,
    ConnectDBRequest,
    ConnectDBResponse,
    DBConnectionItem,
    DBHealthResponse,
    IndexRecommendationsResponse,
    IssueResolveResponse,
    IssueResponse,
    MCPStatusResponse,
    SandboxQueryRequest,
    SandboxQueryResponse,
    SchemaResponse,
)
from backend.connectors import PostgresConnector, CouchbaseConnector, is_dangerous_query
from backend.core.db_registry import get_registry
from backend.core.health_monitor import HealthMonitor
from backend.core.schema_cache import get_schema_cache
from backend.core.chat_session import get_session_store
from backend.core.report_parser import parse_html_report
from backend.mcp.bridge import get_mcp_status
from backend.time_travel.issue_history import get_issue_history

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# --- State ---

_active_connections: dict[str, dict[str, Any]] = {}
_connections_lock = threading.Lock()

_orchestrator: Any = None
_orchestrator_lock = threading.Lock()

_llm_router: Any = None
_llm_router_lock = threading.Lock()


# --- Helpers ---


def _sanitize_error(msg: str) -> str:
    """Strip credentials from error messages."""
    if not msg:
        return msg
    # Redact postgresql://user:password@
    out = re.sub(
        r"(postgresql://[^:]+:)([^@]+)(@)",
        r"\1***\3",
        msg,
        flags=re.IGNORECASE,
    )
    # Redact password=, api_key=, etc.
    out = re.sub(r"(?i)(password|api_key|secret|token)[=:]\s*[^\s&]+", r"\1=***", out)
    return out


def _get_orchestrator():
    """Lazy singleton for AgentOrchestrator."""
    global _orchestrator
    with _orchestrator_lock:
        if _orchestrator is None:
            from backend.agents.agent_orchestrator import AgentOrchestrator

            _orchestrator = AgentOrchestrator()
        return _orchestrator


def _get_llm_router():
    """Lazy singleton for LLMRouter."""
    global _llm_router
    with _llm_router_lock:
        if _llm_router is None:
            from backend.core.llm_router import LLMRouter

            _llm_router = LLMRouter()
        return _llm_router


def _build_postgres_dsn(req: ConnectDBRequest) -> str:
    """Build postgresql DSN from ConnectDBRequest."""
    if req.dsn:
        return req.dsn
    host = req.host or "localhost"
    port = req.port or 5432
    database = req.database or "postgres"
    user = quote_plus(req.user or "postgres")
    password = quote_plus(req.password or "")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def _resolve_connection(connection_id: str | None) -> tuple[str | None, dict[str, Any] | None]:
    """Get active connection by id. If None, return first postgres. Returns (conn_id, conn_dict)."""
    with _connections_lock:
        if connection_id:
            conn = _active_connections.get(connection_id)
            return (connection_id if conn else None, conn)
        for cid, c in _active_connections.items():
            if c.get("engine") == "postgres":
                return (cid, c)
        return (None, None)


# --- Connection management ---


@router.post("/connect", response_model=ConnectDBResponse)
async def connect_db(
    req: ConnectDBRequest,
    user: UserContext = Depends(require_permission("db_manage")),
) -> ConnectDBResponse:
    """Connect to a database (postgres or couchbase)."""
    try:
        # If connection_id is provided, look up stored config from registry
        if req.connection_id:
            registry = get_registry()
            stored = registry.get_connection(req.connection_id)
            if stored:
                req.engine = stored.engine
                if stored.engine == "postgres":
                    req.host = req.host or stored.host or None
                    req.port = req.port or stored.port or None
                    req.database = req.database or stored.database or None
                    req.user = req.user or stored.user or None
                    req.password = req.password or stored.password or None
                    req.dsn = req.dsn or (stored.dsn if stored.host else None)
                elif stored.engine == "couchbase":
                    req.connection_string = req.connection_string or stored.connection_string or None
                    req.bucket = req.bucket or stored.bucket or None
                    req.username = req.username or stored.username or None
                    req.password = req.password or stored.password or None

        engine = (req.engine or "postgres").lower()
        connector = None

        if engine == "postgres":
            dsn = req.dsn or _build_postgres_dsn(req)
            connector = PostgresConnector(dsn=dsn)
        elif engine == "couchbase":
            if not CouchbaseConnector:
                raise HTTPException(
                    status_code=501,
                    detail="Couchbase connector not available (SDK not installed)",
                )
            connector = CouchbaseConnector(
                connection_string=req.connection_string,
                bucket=req.bucket,
                username=req.username,
                password=req.password,
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported engine: {engine}")

        result = await connector.connect()
        if not result.success:
            return ConnectDBResponse(
                success=False,
                message=_sanitize_error(result.message),
                details=result.details,
            )

        conn_id = str(uuid.uuid4())
        name = f"Active ({engine})"
        dsn_or_config = (
            req.dsn or _build_postgres_dsn(req)
            if engine == "postgres"
            else (req.connection_string or "")
        )

        with _connections_lock:
            _active_connections[conn_id] = {
                "engine": engine,
                "connector": connector,
                "dsn": dsn_or_config if engine == "postgres" else None,
                "config": (
                    {
                        "connection_string": req.connection_string,
                        "bucket": req.bucket,
                        "username": req.username,
                    }
                    if engine == "couchbase"
                    else None
                ),
                "name": name,
            }

        # Auto-health-check after connect
        try:
            monitor = HealthMonitor()
            if engine == "postgres":
                metrics = await monitor.collect_postgres_metrics(connector)
            elif engine == "couchbase":
                metrics = await monitor.collect_couchbase_metrics(connector)
            else:
                metrics = {}
            if metrics:
                computed = monitor.compute_health_score(metrics)
                raw_alerts = computed.get("alerts", [])
                if raw_alerts:
                    issues_store = get_issue_history()
                    for alert in raw_alerts:
                        from backend.scheduler.monitoring_job import _detect_category

                        cat = _detect_category(alert)
                        if isinstance(alert, dict):
                            issues_store.record(
                                severity=alert.get("severity", "medium"),
                                title=alert.get("title", "Health alert"),
                                description=alert.get("description", ""),
                                source="auto_connect_check",
                                category=cat,
                                connection_id=conn_id,
                            )
                        else:
                            issues_store.record(
                                severity="medium",
                                title="Health alert",
                                description=str(alert),
                                source="auto_connect_check",
                                category=cat,
                                connection_id=conn_id,
                            )
        except Exception as e:
            logger.debug("Auto health check failed: %s", e)

        return ConnectDBResponse(
            success=True,
            message=result.message,
            connection_id=conn_id,
            details=result.details,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Connect failed")
        raise HTTPException(
            status_code=500,
            detail=_sanitize_error(str(e)),
        )


@router.post("/disconnect/{connection_id}")
async def disconnect_db(
    connection_id: str,
    user: UserContext = Depends(require_permission("db_manage")),
) -> dict[str, Any]:
    """Disconnect a database by connection_id."""
    try:
        with _connections_lock:
            conn = _active_connections.pop(connection_id, None)
        if not conn:
            raise HTTPException(status_code=404, detail="Connection not found")

        connector = conn.get("connector")
        if connector:
            await connector.disconnect()
        return {"success": True, "message": "Disconnected"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Disconnect failed")
        raise HTTPException(status_code=500, detail=_sanitize_error(str(e)))


@router.get("/connections", response_model=list[DBConnectionItem])
async def list_connections(
    user: UserContext = Depends(require_permission("view_schema")),
) -> list[DBConnectionItem]:
    """List all connections from DBRegistry and active connections."""
    try:
        items: list[DBConnectionItem] = []
        seen_ids: set[str] = set()

        registry = get_registry()
        for c in registry.list_connections():
            items.append(
                DBConnectionItem(
                    id=c.id,
                    name=c.name,
                    engine=c.engine,
                    default=c.default,
                )
            )
            seen_ids.add(c.id)

        with _connections_lock:
            for conn_id, data in _active_connections.items():
                if conn_id not in seen_ids:
                    items.append(
                        DBConnectionItem(
                            id=conn_id,
                            name=data.get("name", f"Active ({data.get('engine', 'unknown')})"),
                            engine=data.get("engine", "postgres"),
                            default=False,
                        )
                    )

        return items
    except Exception as e:
        logger.exception("List connections failed")
        raise HTTPException(status_code=500, detail=_sanitize_error(str(e)))


@router.post("/connections/add", response_model=DBConnectionItem)
async def add_connection(
    req: AddConnectionRequest,
    user: UserContext = Depends(require_permission("db_manage")),
) -> DBConnectionItem:
    """Add custom connection to registry."""
    try:
        registry = get_registry()
        conn = registry.add_connection(
            name=req.name,
            engine=req.engine,
            default=req.default,
            host=req.host or "",
            port=req.port or 0,
            database=req.database or "",
            user=req.user or "",
            password=req.password or "",
            connection_string=req.connection_string or "",
            bucket=req.bucket or "",
            username=req.username or "",
        )
        return DBConnectionItem(
            id=conn.id,
            name=conn.name,
            engine=conn.engine,
            default=conn.default,
        )
    except Exception as e:
        logger.exception("Add connection failed")
        raise HTTPException(status_code=500, detail=_sanitize_error(str(e)))


@router.delete("/connections/{connection_id}")
async def remove_connection(
    connection_id: str,
    user: UserContext = Depends(require_permission("db_manage")),
) -> dict[str, Any]:
    """Remove connection from registry (custom connections only)."""
    try:
        registry = get_registry()
        removed = registry.remove_connection(connection_id)
        if not removed:
            raise HTTPException(status_code=404, detail="Connection not found or not removable")
        return {"success": True, "message": "Connection removed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Remove connection failed")
        raise HTTPException(status_code=500, detail=_sanitize_error(str(e)))


# --- Schema ---


@router.get("/schema", response_model=SchemaResponse)
async def get_schema(
    connection_id: str | None = None,
    user: UserContext = Depends(require_permission("view_schema")),
) -> SchemaResponse:
    """Fetch schema metadata from active postgres connection (uses schema cache)."""
    try:
        conn_id, conn = _resolve_connection(connection_id)
        if not conn:
            raise HTTPException(
                status_code=400,
                detail="No active postgres connection. Connect first via POST /api/connect",
            )
        engine = conn.get("engine")
        if engine != "postgres":
            raise HTTPException(
                status_code=400,
                detail="Schema endpoint requires an active postgres connection",
            )

        connector = conn.get("connector")
        dsn = conn.get("dsn", "")
        cache = get_schema_cache()

        tables = cache.get(dsn)
        if tables is None:
            tables = await connector.fetch_schema_metadata()
            cache.set(dsn, tables)

        return SchemaResponse(tables=tables, connection_id=conn_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Get schema failed")
        raise HTTPException(status_code=500, detail=_sanitize_error(str(e)))


# --- Analysis ---


@router.post("/analyze-query", response_model=AnalyzeQueryResponse)
async def analyze_query(
    req: AnalyzeQueryRequest,
    user: UserContext = Depends(require_permission("analyze")),
) -> AnalyzeQueryResponse:
    """Run analysis pipeline: build context from query + schema, run orchestrator."""
    try:
        conn_id, conn = _resolve_connection(req.connection_id)
        if not conn or conn.get("engine") != "postgres":
            raise HTTPException(
                status_code=400,
                detail="Active postgres connection required. Connect first.",
            )

        connector = conn.get("connector")
        dsn = conn.get("dsn", "")
        cache = get_schema_cache()

        tables = cache.get(dsn)
        if tables is None:
            tables = await connector.fetch_schema_metadata()
            cache.set(dsn, tables)

        context: dict[str, Any] = {
            "query": req.query,
            "schema_metadata": tables,
        }

        mode = (req.mode or "full").lower()
        orchestrator = _get_orchestrator()

        if mode == "full":
            result = await orchestrator.run_full(context)
        elif mode == "query_only":
            result = await orchestrator.run_query_only(context)
        elif mode == "index_only":
            result = await orchestrator.run_index_only(context)
        else:
            result = await orchestrator.run_full(context)
            mode = "full"

        run_id = result.get("_pipeline_run_id")
        timing = result.get("_timing", {})

        results: dict[str, Any] = {}
        for k, v in result.items():
            if not k.startswith("_"):
                results[k] = v

        return AnalyzeQueryResponse(
            run_id=run_id,
            mode=mode,
            results=results,
            timing=timing,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Analyze query failed")
        raise HTTPException(status_code=500, detail=_sanitize_error(str(e)))


@router.get("/index-recommendations", response_model=IndexRecommendationsResponse)
async def get_index_recommendations(
    connection_id: str | None = None,
    user: UserContext = Depends(require_permission("analyze")),
) -> IndexRecommendationsResponse:
    """Run index-only pipeline and return recommendations."""
    try:
        conn_id, conn = _resolve_connection(connection_id)
        if not conn or conn.get("engine") != "postgres":
            raise HTTPException(
                status_code=400,
                detail="Active postgres connection required.",
            )

        connector = conn.get("connector")
        dsn = conn.get("dsn", "")
        cache = get_schema_cache()

        tables = cache.get(dsn)
        if tables is None:
            tables = await connector.fetch_schema_metadata()
            cache.set(dsn, tables)

        context: dict[str, Any] = {"schema_metadata": tables}
        orchestrator = _get_orchestrator()
        result = await orchestrator.run_index_only(context)

        recommendations: list[dict[str, Any]] = []
        index_advisor = result.get("index_advisor")
        if index_advisor and isinstance(index_advisor, dict):
            raw = index_advisor.get("raw_response", "")
            if raw:
                recommendations.append({"raw_response": raw})
        elif index_advisor:
            recommendations.append({"raw_response": str(index_advisor)})

        return IndexRecommendationsResponse(recommendations=recommendations)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Index recommendations failed")
        raise HTTPException(status_code=500, detail=_sanitize_error(str(e)))


# --- Health ---


@router.get("/db-health", response_model=DBHealthResponse)
async def get_db_health(
    connection_id: str | None = None,
    user: UserContext = Depends(require_permission("view_health")),
) -> DBHealthResponse:
    """Collect health metrics from active connection and compute score."""
    try:
        conn_id, conn = _resolve_connection(connection_id)
        if not conn:
            raise HTTPException(
                status_code=400,
                detail="No active connection. Connect first.",
            )

        connector = conn.get("connector")
        engine = conn.get("engine")
        monitor = HealthMonitor()

        if engine == "postgres":
            metrics = await monitor.collect_postgres_metrics(connector)
        elif engine == "couchbase":
            metrics = await monitor.collect_couchbase_metrics(connector)
        else:
            raise HTTPException(status_code=400, detail=f"Health not supported for engine: {engine}")

        computed = monitor.compute_health_score(metrics)
        score = int(round(computed["score"]))
        status = computed["status"]
        raw_metrics = computed.get("metrics", {})
        alerts_raw = computed.get("alerts", [])

        return DBHealthResponse(
            score=score,
            status=status,
            metrics=[raw_metrics] if isinstance(raw_metrics, dict) else raw_metrics,
            alerts=[{"message": a} for a in alerts_raw],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("DB health failed")
        raise HTTPException(status_code=500, detail=_sanitize_error(str(e)))


@router.get("/db-health/all", response_model=AllDBHealthResponse)
async def get_all_db_health(
    user: UserContext = Depends(require_permission("view_health")),
) -> AllDBHealthResponse:
    """Collect health metrics from ALL active connections."""
    try:
        result: dict[str, DBHealthResponse] = {}
        monitor = HealthMonitor()

        with _connections_lock:
            active = dict(_active_connections)

        for conn_id, conn in active.items():
            try:
                connector = conn.get("connector")
                engine = conn.get("engine")
                if engine == "postgres":
                    metrics = await monitor.collect_postgres_metrics(connector)
                elif engine == "couchbase":
                    metrics = await monitor.collect_couchbase_metrics(connector)
                else:
                    continue
                computed = monitor.compute_health_score(metrics)
                score = int(round(computed["score"]))
                status = computed["status"]
                raw_metrics = computed.get("metrics", {})
                alerts_raw = computed.get("alerts", [])
                result[conn_id] = DBHealthResponse(
                    score=score,
                    status=status,
                    metrics=[raw_metrics] if isinstance(raw_metrics, dict) else raw_metrics,
                    alerts=[{"message": a} for a in alerts_raw],
                )
            except Exception as e:
                logger.debug("Health check failed for %s: %s", conn_id, e)

        return AllDBHealthResponse(connections=result)
    except Exception as e:
        logger.exception("All DB health failed")
        raise HTTPException(status_code=500, detail=_sanitize_error(str(e)))


@router.get("/mcp-status", response_model=MCPStatusResponse)
async def mcp_status() -> MCPStatusResponse:
    """Return MCP config status."""
    try:
        status = get_mcp_status()
        return MCPStatusResponse(
            postgres=status.get("postgres", {}),
            couchbase=status.get("couchbase", {}),
        )
    except Exception as e:
        logger.exception("MCP status failed")
        raise HTTPException(status_code=500, detail=_sanitize_error(str(e)))


# --- Issues ---


@router.get("/issues")
async def list_issues(
    category: str | None = None,
    severity: str | None = None,
    user: UserContext = Depends(require_permission("view_health")),
) -> list[IssueResponse]:
    """Return all detected issues, optionally filtered by category or severity."""
    try:
        store = get_issue_history()
        if category:
            raw = store.get_issues_by_category(category)
        elif severity:
            raw = store.get_issues_by_severity(severity)
        else:
            raw = store.get_all_issues()
        return [
            IssueResponse(
                id=i.id,
                timestamp=i.timestamp,
                severity=i.severity,
                title=i.title,
                description=i.description,
                source=i.source,
                category=getattr(i, "category", "other"),
                resolved=i.resolved,
                resolved_at=i.resolved_at,
                connection_id=getattr(i, "connection_id", ""),
            )
            for i in raw
        ]
    except Exception as e:
        logger.exception("List issues failed")
        raise HTTPException(status_code=500, detail=_sanitize_error(str(e)))


@router.post("/issues/{issue_id}/resolve")
async def resolve_issue(
    issue_id: str,
    user: UserContext = Depends(require_permission("db_manage")),
) -> IssueResolveResponse:
    """Mark an issue as resolved."""
    try:
        store = get_issue_history()
        resolved = store.resolve(issue_id)
        if not resolved:
            raise HTTPException(status_code=404, detail="Issue not found")
        return IssueResolveResponse(success=True, message="Issue resolved")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Resolve issue failed")
        raise HTTPException(status_code=500, detail=_sanitize_error(str(e)))


# --- Chat ---


async def _enrich_session_context(session, connection_id: str | None = None) -> None:
    """Inject active connection's schema and health into the chat session."""
    conn_id, conn = _resolve_connection(connection_id)
    if not conn:
        return

    safe = {k: v for k, v in conn.items() if k not in ("connector", "dsn")}
    safe["connection_id"] = conn_id
    session.set_connection_info(safe)

    connector = conn.get("connector")
    engine = conn.get("engine")
    dsn = conn.get("dsn", "")

    if engine == "postgres" and dsn and not session.schema_context:
        cache = get_schema_cache()
        tables = cache.get(dsn)
        if not tables and connector:
            try:
                tables = await connector.fetch_schema_metadata()
                if tables:
                    cache.set(dsn, tables)
            except Exception:
                pass
        if tables:
            schema_lines = []
            for t in tables[:50]:
                tname = t.get("table_name", "?")
                cols = t.get("columns", [])
                col_str = ", ".join(
                    f"{c.get('column_name', '?')} {c.get('data_type', '?')}" for c in cols[:20]
                )
                pks = t.get("primary_keys", [])
                fks = t.get("foreign_keys", [])
                schema_lines.append(f"Table {tname}: ({col_str})")
                if pks:
                    schema_lines.append(f"  PK: {', '.join(pks)}")
                for fk in fks[:5]:
                    schema_lines.append(
                        f"  FK: {fk.get('column','')} -> {fk.get('references_table','')}.{fk.get('references_column','')}"
                    )
            session.set_schema("\n".join(schema_lines))

    if not session.health_context and connector:
        try:
            monitor = HealthMonitor()
            if engine == "postgres":
                metrics = await monitor.collect_postgres_metrics(connector)
            elif engine == "couchbase":
                metrics = await monitor.collect_couchbase_metrics(connector)
            else:
                metrics = {}
            if metrics:
                computed = monitor.compute_health_score(metrics)
                health_lines = [
                    f"Score: {computed.get('score', 0)}",
                    f"Status: {computed.get('status', 'unknown')}",
                ]
                raw_metrics = computed.get("metrics", {})
                if isinstance(raw_metrics, dict):
                    for k, v in raw_metrics.items():
                        health_lines.append(f"  {k}: {v}")
                alerts = computed.get("alerts", [])
                if alerts:
                    health_lines.append("Alerts:")
                    for a in alerts:
                        health_lines.append(f"  - {a}")
                session.set_health("\n".join(health_lines))
        except Exception:
            pass


@router.post("/chat", response_model=ChatResponse)
async def chat(
    message: str = Form(...),
    session_id: str | None = Form(None),
    connection_id: str | None = Form(None),
    files: list[UploadFile] = File(default=[]),
    user: UserContext = Depends(require_permission("chat")),
) -> ChatResponse:
    """
    Chat with full session context. Accepts multipart/form-data.
    - message: user message text
    - session_id: reuse existing session (optional)
    - connection_id: active DB connection to inject context from (optional)
    - files: HTML report files to upload and analyze in context (optional)
    """
    try:
        store = get_session_store()
        session = store.get_or_create(session_id)

        await _enrich_session_context(session, connection_id)

        for upload_file in files:
            if upload_file and upload_file.filename:
                raw = await upload_file.read()
                html_content = raw.decode("utf-8", errors="replace")
                parsed = parse_html_report(html_content, upload_file.filename)
                session.add_report(upload_file.filename, parsed)
                session.add_message(
                    "system",
                    f"[Report uploaded: {upload_file.filename} — {len(parsed)} chars of extracted content]",
                )

        session.add_message("user", message)

        llm = _get_llm_router()
        from backend.core.config import get_settings

        settings = get_settings()
        messages = session.get_messages_for_llm()
        reply = await llm.generate(messages, flow_name=settings.AMAIZ_CHAT_FLOW_NAME)

        session.add_message("assistant", reply)

        return ChatResponse(
            reply=reply,
            session_id=session.session_id,
            context_summary=session.context_summary(),
        )
    except Exception as e:
        logger.exception("Chat failed")
        raise HTTPException(status_code=500, detail=_sanitize_error(str(e)))


# --- Sandbox ---


@router.post("/sandbox", response_model=SandboxQueryResponse)
async def sandbox_query(
    req: SandboxQueryRequest,
    user: UserContext = Depends(require_permission("sandbox_access")),
) -> SandboxQueryResponse:
    """
    Execute query in sandbox with transaction isolation and automatic rollback.
    Blocks dangerous DDL/DML. Uses a separate connection in a rolled-back transaction
    so production data is never modified.
    """
    try:
        if is_dangerous_query(req.query):
            return SandboxQueryResponse(
                success=False,
                error="Destructive or write operations are not allowed in sandbox",
            )

        conn_id, conn = _resolve_connection(req.connection_id)
        if not conn:
            raise HTTPException(
                status_code=400,
                detail="No active connection. Connect first.",
            )

        engine = conn.get("engine")

        if engine == "postgres":
            rows = await _sandbox_postgres(conn, req.query)
        elif engine == "couchbase":
            connector = conn.get("connector")
            rows = await connector.execute_read_only(req.query)
        else:
            raise HTTPException(status_code=400, detail=f"Sandbox not supported for: {engine}")

        if not isinstance(rows, list):
            rows = list(rows) if rows else []

        return SandboxQueryResponse(
            success=True,
            rows=rows[:_SANDBOX_MAX_ROWS],
            row_count=len(rows),
        )
    except HTTPException:
        raise
    except ValueError as e:
        return SandboxQueryResponse(success=False, error=str(e))
    except Exception as e:
        logger.exception("Sandbox query failed")
        return SandboxQueryResponse(
            success=False,
            error=_sanitize_error(str(e)),
        )


_SANDBOX_MAX_ROWS = 200
_SANDBOX_TIMEOUT = 30.0


async def _sandbox_postgres(conn: dict[str, Any], query: str) -> list[dict[str, Any]]:
    """
    Execute query in an isolated postgres transaction that is always rolled back.
    Uses a fresh connection so the main connection is never affected.
    """
    import asyncio
    import asyncpg

    dsn = conn.get("dsn", "")
    if not dsn:
        raise ValueError("No DSN available for sandbox execution")

    sandbox_conn: asyncpg.Connection | None = None
    try:
        sandbox_conn = await asyncio.wait_for(
            asyncpg.connect(dsn),
            timeout=_SANDBOX_TIMEOUT,
        )
        tx = sandbox_conn.transaction(readonly=True)
        await tx.start()
        try:
            rows = await asyncio.wait_for(
                sandbox_conn.fetch(query),
                timeout=_SANDBOX_TIMEOUT,
            )
            return [dict(r) for r in rows]
        finally:
            await tx.rollback()
    finally:
        if sandbox_conn:
            await sandbox_conn.close()
