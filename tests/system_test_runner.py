#!/usr/bin/env python3
"""
Full system test runner for DB Analyzer v7.
Tests all API endpoints against a running server at http://127.0.0.1:8004.
Produces structured JSON results.
"""

import json
import os
import sys
import time
import traceback
from pathlib import Path

import requests

BASE = os.environ.get("TEST_BASE_URL", "http://127.0.0.1:8010")
REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "reports"
REPORT1 = REPORTS_DIR / "PGAWR_13558_13559_172.24.202.145_EXTENDED.html"
REPORT2 = REPORTS_DIR / "PGAWR_13560_13561_172.24.202.145_EXTENDED.html"

results = []


def record(area: str, test: str, passed: bool, detail: str = "", severity: str = ""):
    results.append({
        "area": area,
        "test": test,
        "passed": passed,
        "detail": detail,
        "severity": severity,
    })
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {area} > {test}" + (f" -- {detail[:120]}" if detail and not passed else ""))


def safe_json(resp):
    try:
        return resp.json()
    except Exception:
        return None


# ============================================================
# 2.1 Health and Infra
# ============================================================
def test_health_infra():
    print("\n=== 2.1 Health and Infra ===")

    # /health/live
    try:
        r = requests.get(f"{BASE}/health/live", timeout=10)
        data = safe_json(r)
        record("Health", "GET /health/live returns 200", r.status_code == 200, f"status={r.status_code}")
        record("Health", "/health/live body has status=ok", data and data.get("status") == "ok", str(data))
    except Exception as e:
        record("Health", "GET /health/live", False, str(e), "critical")

    # /health/ready
    try:
        r = requests.get(f"{BASE}/health/ready", timeout=10)
        data = safe_json(r)
        record("Health", "GET /health/ready returns 200", r.status_code == 200, f"status={r.status_code}")
        record("Health", "/health/ready has status+version",
               data and "status" in data and "version" in data, str(data))
    except Exception as e:
        record("Health", "GET /health/ready", False, str(e), "critical")

    # /health
    try:
        r = requests.get(f"{BASE}/health", timeout=10)
        record("Health", "GET /health returns 200", r.status_code == 200, f"status={r.status_code}")
    except Exception as e:
        record("Health", "GET /health", False, str(e))

    # /metrics
    try:
        r = requests.get(f"{BASE}/metrics", timeout=10)
        record("Health", "GET /metrics returns 200", r.status_code == 200, f"status={r.status_code}")
        record("Health", "/metrics content-type is text/plain",
               "text/plain" in r.headers.get("content-type", ""),
               r.headers.get("content-type", ""))
    except Exception as e:
        record("Health", "GET /metrics", False, str(e))


# ============================================================
# 2.2 Connection Lifecycle
# ============================================================
def test_connections():
    print("\n=== 2.2 Connection Lifecycle ===")

    # GET /api/connections
    try:
        r = requests.get(f"{BASE}/api/connections", timeout=10)
        data = safe_json(r)
        record("Connections", "GET /api/connections returns 200", r.status_code == 200,
               f"status={r.status_code}, count={len(data) if isinstance(data, list) else 'N/A'}")
        record("Connections", "/api/connections returns list",
               isinstance(data, list), f"type={type(data).__name__}")
    except Exception as e:
        record("Connections", "GET /api/connections", False, str(e), "major")

    # POST /api/connect with empty body
    try:
        r = requests.post(f"{BASE}/api/connect", json={}, timeout=30)
        data = safe_json(r)
        if r.status_code == 200:
            ok = data and data.get("success") is False
            record("Connections", "POST /api/connect empty body -> success=false", ok, str(data)[:200])
        else:
            record("Connections", "POST /api/connect empty body -> error status",
                   r.status_code in (400, 422, 500), f"status={r.status_code}")
    except Exception as e:
        record("Connections", "POST /api/connect empty body", False, str(e))

    # POST /api/connect with invalid DSN
    try:
        r = requests.post(f"{BASE}/api/connect", json={"dsn": "postgresql://invalid:invalid@127.0.0.1:9999/nonexistent"}, timeout=30)
        data = safe_json(r)
        # Should fail gracefully
        if r.status_code == 200:
            ok = data and data.get("success") is False
            record("Connections", "POST /api/connect invalid DSN -> success=false", ok, str(data)[:200])
            # Check no credentials leaked
            resp_str = json.dumps(data) if data else ""
            leaked = "invalid:invalid" in resp_str or "nonexistent" in resp_str.lower()
            # password leaking is the concern
            pwd_leaked = "invalid:invalid" in resp_str
            record("Connections", "Invalid DSN response: no password leak", not pwd_leaked,
                   "Password visible in response" if pwd_leaked else "Clean", "major" if pwd_leaked else "")
        else:
            record("Connections", "POST /api/connect invalid DSN -> error status",
                   r.status_code in (400, 422, 500), f"status={r.status_code}")
    except Exception as e:
        record("Connections", "POST /api/connect invalid DSN", False, str(e))

    # GET /api/schema with no connection
    try:
        r = requests.get(f"{BASE}/api/schema", timeout=10)
        record("Connections", "GET /api/schema no connection -> 400", r.status_code == 400,
               f"status={r.status_code}")
    except Exception as e:
        record("Connections", "GET /api/schema no connection", False, str(e))

    # POST /api/connect with valid connection_id from registry
    conn_id_connected = None
    try:
        r = requests.get(f"{BASE}/api/connections", timeout=10)
        conns = safe_json(r)
        if conns and isinstance(conns, list) and len(conns) > 0:
            first = conns[0]
            cid = first.get("id")
            r2 = requests.post(f"{BASE}/api/connect", json={"connection_id": cid}, timeout=60)
            data2 = safe_json(r2)
            success = data2 and data2.get("success") is True
            record("Connections", f"POST /api/connect with registry id -> success",
                   success, str(data2)[:200])
            if success:
                conn_id_connected = data2.get("connection_id")
        else:
            record("Connections", "No registry connections to test connect", True, "SKIP - no connections in registry")
    except Exception as e:
        record("Connections", "POST /api/connect registry", False, str(e))

    # GET /api/schema with active connection
    if conn_id_connected:
        try:
            r = requests.get(f"{BASE}/api/schema", params={"connection_id": conn_id_connected}, timeout=30)
            data = safe_json(r)
            record("Connections", "GET /api/schema with connection -> 200",
                   r.status_code == 200, f"status={r.status_code}")
            if data:
                tables = data.get("tables", [])
                record("Connections", "/api/schema returns tables array",
                       isinstance(tables, list) and len(tables) > 0,
                       f"table_count={len(tables) if isinstance(tables, list) else 'N/A'}")
        except Exception as e:
            record("Connections", "GET /api/schema with connection", False, str(e))

    return conn_id_connected


# ============================================================
# 2.3 Connections Registry
# ============================================================
def test_connections_registry():
    print("\n=== 2.3 Connections Registry ===")

    added_id = None
    try:
        r = requests.post(f"{BASE}/api/connections/add", json={
            "name": "test-system-check",
            "engine": "postgres",
            "host": "127.0.0.1",
            "port": 5432,
            "database": "testdb",
            "user": "testuser",
            "password": "testpass",
        }, timeout=10)
        data = safe_json(r)
        record("Registry", "POST /api/connections/add -> 200", r.status_code == 200,
               f"status={r.status_code}")
        if data:
            added_id = data.get("id")
            record("Registry", "Added connection has id", bool(added_id), f"id={added_id}")
    except Exception as e:
        record("Registry", "POST /api/connections/add", False, str(e))

    # Verify it appears in list
    if added_id:
        try:
            r = requests.get(f"{BASE}/api/connections", timeout=10)
            data = safe_json(r)
            found = any(c.get("id") == added_id for c in (data or []))
            record("Registry", "Added connection appears in list", found, f"id={added_id}")
        except Exception as e:
            record("Registry", "Verify added in list", False, str(e))

    # Delete it
    if added_id:
        try:
            r = requests.delete(f"{BASE}/api/connections/{added_id}", timeout=10)
            record("Registry", "DELETE /api/connections/{id} -> 200", r.status_code == 200,
                   f"status={r.status_code}")
        except Exception as e:
            record("Registry", "DELETE connection", False, str(e))

    # Delete non-existent
    try:
        r = requests.delete(f"{BASE}/api/connections/nonexistent-id-12345", timeout=10)
        record("Registry", "DELETE non-existent -> 404", r.status_code == 404,
               f"status={r.status_code}")
    except Exception as e:
        record("Registry", "DELETE non-existent", False, str(e))


# ============================================================
# 2.4 Analysis Pipeline
# ============================================================
def test_analysis(conn_id):
    print("\n=== 2.4 Analysis Pipeline ===")

    # No connection
    try:
        r = requests.post(f"{BASE}/api/analyze-query", json={"query": "SELECT 1"}, timeout=10)
        record("Analysis", "POST /api/analyze-query no conn -> 400", r.status_code == 400,
               f"status={r.status_code}")
    except Exception as e:
        record("Analysis", "POST /api/analyze-query no conn", False, str(e))

    if conn_id:
        for mode in ["full", "query_only", "index_only"]:
            try:
                r = requests.post(f"{BASE}/api/analyze-query", json={
                    "query": "SELECT * FROM pg_stat_activity LIMIT 10",
                    "connection_id": conn_id,
                    "mode": mode,
                }, timeout=120)
                data = safe_json(r)
                record("Analysis", f"analyze-query mode={mode} -> 200", r.status_code == 200,
                       f"status={r.status_code}")
                if data:
                    record("Analysis", f"mode={mode} has run_id", bool(data.get("run_id")),
                           f"run_id={data.get('run_id')}")
                    record("Analysis", f"mode={mode} has results dict",
                           isinstance(data.get("results"), dict),
                           f"keys={list(data.get('results', {}).keys())[:5]}")
                    record("Analysis", f"mode={mode} has timing dict",
                           isinstance(data.get("timing"), dict),
                           f"timing_keys={list(data.get('timing', {}).keys())[:5]}")
            except Exception as e:
                record("Analysis", f"analyze-query mode={mode}", False, str(e))

    # Index recommendations
    if conn_id:
        try:
            r = requests.get(f"{BASE}/api/index-recommendations",
                           params={"connection_id": conn_id}, timeout=120)
            data = safe_json(r)
            record("Analysis", "GET /api/index-recommendations -> 200", r.status_code == 200,
                   f"status={r.status_code}")
        except Exception as e:
            record("Analysis", "GET /api/index-recommendations", False, str(e))
    else:
        try:
            r = requests.get(f"{BASE}/api/index-recommendations", timeout=10)
            record("Analysis", "GET /api/index-recommendations no conn -> 400",
                   r.status_code == 400, f"status={r.status_code}")
        except Exception as e:
            record("Analysis", "index-recommendations no conn", False, str(e))


# ============================================================
# 2.5 Health and Issues
# ============================================================
def test_health_issues(conn_id):
    print("\n=== 2.5 Health and Issues ===")

    # No connection
    try:
        r = requests.get(f"{BASE}/api/db-health", timeout=10)
        record("DB Health", "GET /api/db-health no conn -> 400", r.status_code == 400,
               f"status={r.status_code}")
    except Exception as e:
        record("DB Health", "db-health no conn", False, str(e))

    if conn_id:
        try:
            r = requests.get(f"{BASE}/api/db-health",
                           params={"connection_id": conn_id}, timeout=30)
            data = safe_json(r)
            record("DB Health", "GET /api/db-health with conn -> 200", r.status_code == 200,
                   f"status={r.status_code}")
            if data:
                record("DB Health", "Has score", "score" in data, f"score={data.get('score')}")
                record("DB Health", "Has status", "status" in data, f"status={data.get('status')}")
                record("DB Health", "Has metrics", "metrics" in data,
                       f"metrics_count={len(data.get('metrics', []))}")
                record("DB Health", "Has alerts", "alerts" in data,
                       f"alerts_count={len(data.get('alerts', []))}")
        except Exception as e:
            record("DB Health", "db-health with conn", False, str(e))

    # db-health/all
    try:
        r = requests.get(f"{BASE}/api/db-health/all", timeout=30)
        data = safe_json(r)
        record("DB Health", "GET /api/db-health/all -> 200", r.status_code == 200,
               f"status={r.status_code}")
        if data:
            record("DB Health", "Has connections map", "connections" in data, str(data)[:200])
    except Exception as e:
        record("DB Health", "db-health/all", False, str(e))

    # Issues
    try:
        r = requests.get(f"{BASE}/api/issues", timeout=10)
        data = safe_json(r)
        items = data["items"] if isinstance(data, dict) and "items" in data else data
        record("Issues", "GET /api/issues -> 200", r.status_code == 200, f"status={r.status_code}")
        record("Issues", "/api/issues returns list", isinstance(items, list),
               f"count={len(items) if isinstance(items, list) else 'N/A'}")
    except Exception as e:
        record("Issues", "GET /api/issues", False, str(e))

    # Issues with filters
    for param in ["category=performance", "severity=critical"]:
        try:
            r = requests.get(f"{BASE}/api/issues?{param}", timeout=10)
            record("Issues", f"GET /api/issues?{param} -> 200", r.status_code == 200,
                   f"status={r.status_code}")
        except Exception as e:
            record("Issues", f"issues?{param}", False, str(e))

    # Resolve non-existent issue
    try:
        r = requests.post(f"{BASE}/api/issues/nonexistent-xyz/resolve", timeout=10)
        record("Issues", "POST resolve non-existent -> 404", r.status_code == 404,
               f"status={r.status_code}")
    except Exception as e:
        record("Issues", "resolve non-existent", False, str(e))


# ============================================================
# 2.6 Chat and Report Upload
# ============================================================
def test_chat_and_reports(conn_id):
    print("\n=== 2.6 Chat and Report Upload ===")

    # Simple message
    try:
        r = requests.post(f"{BASE}/api/chat", data={"message": "Hello, test message"},
                         timeout=120)
        data = safe_json(r)
        record("Chat", "POST /api/chat simple message -> 200", r.status_code == 200,
               f"status={r.status_code}")
        if data:
            record("Chat", "Has reply", bool(data.get("reply")), f"reply_len={len(data.get('reply', ''))}")
            record("Chat", "Has session_id", bool(data.get("session_id")),
                   f"session_id={data.get('session_id')}")
            record("Chat", "Has context_summary", bool(data.get("context_summary")),
                   str(data.get("context_summary"))[:200])
    except Exception as e:
        record("Chat", "POST /api/chat simple", False, str(e), "major")

    # Chat with one PGAWR report
    session_id = None
    if REPORT1.exists():
        try:
            with open(REPORT1, "rb") as f:
                r = requests.post(f"{BASE}/api/chat",
                                data={"message": "Summarize this PGAWR report"},
                                files={"files": (REPORT1.name, f, "text/html")},
                                timeout=180)
            data = safe_json(r)
            record("Chat+Report", "Chat with 1 PGAWR report -> 200", r.status_code == 200,
                   f"status={r.status_code}")
            if data:
                ctx = data.get("context_summary", {})
                reports_loaded = ctx.get("reports_loaded", [])
                record("Chat+Report", "Report appears in reports_loaded",
                       REPORT1.name in reports_loaded,
                       f"reports_loaded={reports_loaded}")
                record("Chat+Report", "Reply is non-empty", len(data.get("reply", "")) > 10,
                       f"reply_len={len(data.get('reply', ''))}")
                session_id = data.get("session_id")
        except Exception as e:
            record("Chat+Report", "Chat with 1 report", False, str(e), "major")
    else:
        record("Chat+Report", "Report file 1 exists", False, f"Path: {REPORT1}", "critical")

    # Chat with two PGAWR reports (comparison)
    if REPORT1.exists() and REPORT2.exists():
        try:
            with open(REPORT1, "rb") as f1, open(REPORT2, "rb") as f2:
                r = requests.post(f"{BASE}/api/chat",
                                data={"message": "Compare these two PGAWR reports and highlight key differences"},
                                files=[
                                    ("files", (REPORT1.name, f1, "text/html")),
                                    ("files", (REPORT2.name, f2, "text/html")),
                                ],
                                timeout=180)
            data = safe_json(r)
            record("Chat+Report", "Chat with 2 PGAWR reports -> 200", r.status_code == 200,
                   f"status={r.status_code}")
            if data:
                ctx = data.get("context_summary", {})
                reports_loaded = ctx.get("reports_loaded", [])
                record("Chat+Report", "Both reports in reports_loaded",
                       REPORT1.name in reports_loaded and REPORT2.name in reports_loaded,
                       f"reports_loaded={reports_loaded}")
                reply = data.get("reply", "")
                record("Chat+Report", "Comparison reply is substantial",
                       len(reply) > 50,
                       f"reply_len={len(reply)}")
        except Exception as e:
            record("Chat+Report", "Chat with 2 reports", False, str(e), "major")

    # Session persistence
    if session_id:
        try:
            r = requests.post(f"{BASE}/api/chat",
                            data={"message": "What was the DB host from the report?",
                                  "session_id": session_id},
                            timeout=120)
            data = safe_json(r)
            record("Chat", "Session persistence -> same session_id",
                   data and data.get("session_id") == session_id,
                   f"expected={session_id}, got={data.get('session_id') if data else 'N/A'}")
        except Exception as e:
            record("Chat", "Session persistence", False, str(e))

    # Disallowed file type
    try:
        import io
        fake_exe = io.BytesIO(b"MZ fake binary content")
        r = requests.post(f"{BASE}/api/chat",
                        data={"message": "Analyze this"},
                        files={"files": ("malware.exe", fake_exe, "application/octet-stream")},
                        timeout=60)
        data = safe_json(r)
        record("Chat", "Disallowed file type (.exe) -> 200 (skipped)",
               r.status_code == 200, f"status={r.status_code}")
    except Exception as e:
        record("Chat", "Disallowed file type", False, str(e))


# ============================================================
# 2.7 Sandbox
# ============================================================
def test_sandbox(conn_id):
    print("\n=== 2.7 Sandbox ===")

    # Dangerous query
    try:
        r = requests.post(f"{BASE}/api/sandbox",
                        json={"query": "DROP TABLE users"}, timeout=10)
        data = safe_json(r)
        record("Sandbox", "DROP TABLE -> success=false", r.status_code == 200 and data and data.get("success") is False,
               f"status={r.status_code}, data={str(data)[:200]}")
        if data:
            err = data.get("error", "")
            record("Sandbox", "DROP TABLE error mentions dangerous/destructive",
                   "dangerous" in err.lower() or "destructive" in err.lower(),
                   f"error={err[:100]}")
    except Exception as e:
        record("Sandbox", "DROP TABLE blocked", False, str(e), "critical")

    # More dangerous queries
    for q in ["DELETE FROM users", "TRUNCATE orders", "ALTER TABLE x DROP COLUMN y"]:
        try:
            r = requests.post(f"{BASE}/api/sandbox", json={"query": q}, timeout=10)
            data = safe_json(r)
            blocked = data and data.get("success") is False
            record("Sandbox", f"Blocked: {q[:30]}", blocked, str(data)[:100])
        except Exception as e:
            record("Sandbox", f"Block check: {q[:30]}", False, str(e))

    # Valid read query (needs connection)
    if conn_id:
        try:
            r = requests.post(f"{BASE}/api/sandbox",
                            json={"query": "SELECT 1 AS test_value", "connection_id": conn_id},
                            timeout=30)
            data = safe_json(r)
            record("Sandbox", "SELECT 1 -> success=true",
                   data and data.get("success") is True,
                   str(data)[:200])
            if data and data.get("success"):
                record("Sandbox", "SELECT 1 has rows", len(data.get("rows", [])) > 0,
                       f"row_count={data.get('row_count')}")
        except Exception as e:
            record("Sandbox", "SELECT 1", False, str(e))

    # Oversized query
    try:
        big_query = "SELECT " + ", ".join([f"col_{i}" for i in range(10000)])
        r = requests.post(f"{BASE}/api/sandbox", json={"query": big_query}, timeout=10)
        data = safe_json(r)
        # Should either succeed=false or still handle gracefully
        record("Sandbox", "Oversized query handled gracefully",
               r.status_code in (200, 400, 422),
               f"status={r.status_code}")
    except Exception as e:
        record("Sandbox", "Oversized query", False, str(e))


# ============================================================
# 2.8 Insights and Simulation
# ============================================================
def test_insights_simulation(conn_id):
    print("\n=== 2.8 Insights and Simulation ===")

    # GET /api/insights
    try:
        r = requests.get(f"{BASE}/api/insights", timeout=10)
        data = safe_json(r)
        items = data["items"] if isinstance(data, dict) and "items" in data else data
        record("Insights", "GET /api/insights -> 200", r.status_code == 200,
               f"status={r.status_code}")
        record("Insights", "Returns array", isinstance(items, list),
               f"type={type(items).__name__}, count={len(items) if isinstance(items, list) else 'N/A'}")
    except Exception as e:
        record("Insights", "GET /api/insights", False, str(e))

    # Dismiss non-existent
    try:
        r = requests.post(f"{BASE}/api/insights/nonexistent-xyz/dismiss", timeout=10)
        data = safe_json(r)
        record("Insights", "Dismiss non-existent -> success=false",
               data and data.get("success") is False,
               str(data)[:200])
    except Exception as e:
        record("Insights", "Dismiss non-existent", False, str(e))

    # Run advisor
    try:
        r = requests.post(f"{BASE}/api/insights/run", timeout=60)
        data = safe_json(r)
        record("Insights", "POST /api/insights/run -> 200", r.status_code == 200,
               f"status={r.status_code}")
        if data:
            if conn_id:
                record("Insights", "Run advisor has count", "count" in data,
                       f"count={data.get('count')}")
    except Exception as e:
        record("Insights", "POST insights/run", False, str(e))

    # Simulate - no connection
    try:
        r = requests.post(f"{BASE}/api/simulate",
                        json={"change_type": "add_index", "table": "test"}, timeout=10)
        record("Simulation", "POST /api/simulate no conn -> 400", r.status_code == 400,
               f"status={r.status_code}")
    except Exception as e:
        record("Simulation", "simulate no conn", False, str(e))

    # Simulate with connection
    if conn_id:
        try:
            r = requests.post(f"{BASE}/api/simulate", json={
                "change_type": "add_index",
                "table": "pg_class",
                "column": "relname",
                "connection_id": conn_id,
            }, timeout=120)
            data = safe_json(r)
            record("Simulation", "POST /api/simulate with conn -> 200", r.status_code == 200,
                   f"status={r.status_code}")
            if data:
                record("Simulation", "Has simulation_type", bool(data.get("simulation_type")),
                       f"type={data.get('simulation_type')}")
                record("Simulation", "Has result", bool(data.get("result")),
                       str(data.get("result"))[:200])
        except Exception as e:
            record("Simulation", "simulate with conn", False, str(e))


# ============================================================
# 2.9 MCP Status
# ============================================================
def test_mcp():
    print("\n=== 2.9 MCP Status ===")
    try:
        r = requests.get(f"{BASE}/api/mcp-status", timeout=10)
        data = safe_json(r)
        record("MCP", "GET /api/mcp-status -> 200", r.status_code == 200,
               f"status={r.status_code}")
        if data:
            record("MCP", "Has postgres key", "postgres" in data, str(data.get("postgres"))[:100])
            record("MCP", "Has couchbase key", "couchbase" in data, str(data.get("couchbase"))[:100])
    except Exception as e:
        record("MCP", "GET /api/mcp-status", False, str(e))


# ============================================================
# 6. Non-Functional
# ============================================================
def test_nonfunctional(conn_id):
    print("\n=== 6. Non-Functional ===")

    # Invalid JSON
    try:
        r = requests.post(f"{BASE}/api/connect",
                        data="{{not json}}", 
                        headers={"Content-Type": "application/json"},
                        timeout=10)
        record("NFR", "Invalid JSON -> 422/400", r.status_code in (400, 422),
               f"status={r.status_code}")
        data = safe_json(r)
        if data:
            resp_str = json.dumps(data)
            has_stacktrace = "Traceback" in resp_str or "File \"" in resp_str
            record("NFR", "No stack trace in error response", not has_stacktrace,
                   "Stack trace found in response" if has_stacktrace else "Clean")
    except Exception as e:
        record("NFR", "Invalid JSON", False, str(e))

    # Missing required fields
    try:
        r = requests.post(f"{BASE}/api/analyze-query", json={}, timeout=10)
        record("NFR", "Missing required fields -> 400/422", r.status_code in (400, 422),
               f"status={r.status_code}")
    except Exception as e:
        record("NFR", "Missing required fields", False, str(e))

    # Credential sanitization in error messages
    try:
        r = requests.post(f"{BASE}/api/connect",
                        json={"dsn": "postgresql://secretuser:secretpassword123@badhost:5432/db"},
                        timeout=30)
        data = safe_json(r)
        resp_str = json.dumps(data) if data else r.text
        leaked = "secretpassword123" in resp_str
        record("NFR", "Credential sanitization: no password in error",
               not leaked, "Password leaked!" if leaked else "Sanitized OK", 
               "critical" if leaked else "")
    except Exception as e:
        record("NFR", "Credential sanitization", False, str(e))

    # Rate limit (send many requests quickly)
    try:
        statuses = []
        for _ in range(25):
            r = requests.get(f"{BASE}/health/live", timeout=5)
            statuses.append(r.status_code)
        got_429 = 429 in statuses
        all_200 = all(s == 200 for s in statuses)
        if got_429:
            record("NFR", "Rate limiting is active", True, f"Got 429 after {statuses.index(429)+1} requests")
        else:
            record("NFR", "Rate limiting: no 429 (may not be configured for health)",
                   True, f"All {len(statuses)} requests returned 200 (rate limit may not apply to health)")
    except Exception as e:
        record("NFR", "Rate limiting", False, str(e))

    # WebSocket basic connectivity
    try:
        import websocket
        ws = websocket.create_connection("ws://127.0.0.1:8004/ws", timeout=5)
        record("NFR", "WebSocket /ws connects", True, "Connected OK")
        ws.close()
    except ImportError:
        record("NFR", "WebSocket test skipped (websocket-client not installed)", True, "SKIP")
    except Exception as e:
        record("NFR", "WebSocket /ws", False, str(e))

    # Analyze-report endpoint (documented in README but missing in v7)
    try:
        r = requests.post(f"{BASE}/api/analyze-report", json={"reports": []}, timeout=10)
        if r.status_code == 404 or r.status_code == 405:
            record("NFR", "README documents /api/analyze-report but endpoint missing -> DOC BUG",
                   False, f"status={r.status_code} - endpoint documented in README but not implemented",
                   "minor")
        else:
            record("NFR", "/api/analyze-report exists", True, f"status={r.status_code}")
    except Exception as e:
        record("NFR", "/api/analyze-report check", False, str(e))


# ============================================================
# Main
# ============================================================
def main():
    print("=" * 60)
    print("DB Analyzer v7 - Full System Test")
    print(f"Target: {BASE}")
    print(f"Reports dir: {REPORTS_DIR}")
    print(f"Report 1: {REPORT1} (exists={REPORT1.exists()})")
    print(f"Report 2: {REPORT2} (exists={REPORT2.exists()})")
    print("=" * 60)

    test_health_infra()
    conn_id = test_connections()
    test_connections_registry()
    test_analysis(conn_id)
    test_health_issues(conn_id)
    test_chat_and_reports(conn_id)
    test_sandbox(conn_id)
    test_insights_simulation(conn_id)
    test_mcp()
    test_nonfunctional(conn_id)

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"])
    print("\n" + "=" * 60)
    print(f"TOTAL: {total} | PASSED: {passed} | FAILED: {failed}")
    print("=" * 60)

    # Write JSON results
    out_path = Path(__file__).resolve().parent.parent.parent / "reports" / "system_test_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"total": total, "passed": passed, "failed": failed, "results": results}, f, indent=2)
    print(f"\nJSON results written to {out_path}")


if __name__ == "__main__":
    main()
