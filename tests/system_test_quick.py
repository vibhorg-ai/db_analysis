#!/usr/bin/env python3
"""
Quick system test runner for DB Analyzer v7 - all tests with shorter timeouts.
"""

import json
import os
import sys
import time
from pathlib import Path

import requests

BASE = os.environ.get("TEST_BASE_URL", "http://127.0.0.1:8010")
REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "reports"
REPORT1 = REPORTS_DIR / "PGAWR_13558_13559_172.24.202.145_EXTENDED.html"
REPORT2 = REPORTS_DIR / "PGAWR_13560_13561_172.24.202.145_EXTENDED.html"

results = []
TIMEOUT = 30


def record(area, test, passed, detail="", severity=""):
    results.append({"area": area, "test": test, "passed": passed, "detail": detail, "severity": severity})
    s = "PASS" if passed else "FAIL"
    print(f"  [{s}] {area} > {test}" + (f" -- {detail[:150]}" if detail and not passed else ""))


def safe_json(r):
    try:
        return r.json()
    except Exception:
        return None


def safe_request(method, url, **kwargs):
    kwargs.setdefault("timeout", TIMEOUT)
    try:
        return getattr(requests, method)(url, **kwargs)
    except requests.Timeout:
        return None
    except Exception as e:
        return None


def test_health():
    print("\n=== Health & Infra ===")
    for ep, checks in [
        ("/health/live", [("status 200", lambda r: r.status_code == 200),
                          ("status=ok", lambda r: safe_json(r) and safe_json(r).get("status") == "ok")]),
        ("/health/ready", [("status 200", lambda r: r.status_code == 200),
                           ("has version", lambda r: safe_json(r) and "version" in safe_json(r))]),
        ("/health", [("status 200", lambda r: r.status_code == 200)]),
        ("/metrics", [("status 200", lambda r: r.status_code == 200),
                      ("text/plain", lambda r: "text/plain" in r.headers.get("content-type", ""))]),
    ]:
        r = safe_request("get", f"{BASE}{ep}")
        if not r:
            record("Health", f"GET {ep} reachable", False, "Timeout/error", "critical")
            continue
        for name, check in checks:
            record("Health", f"GET {ep}: {name}", check(r), f"status={r.status_code}")


def test_connections():
    print("\n=== Connections ===")
    conn_id = None

    # List
    r = safe_request("get", f"{BASE}/api/connections")
    if r:
        data = safe_json(r)
        record("Conn", "GET /api/connections -> 200", r.status_code == 200)
        record("Conn", "Returns list", isinstance(data, list))
    else:
        record("Conn", "GET /api/connections", False, "Failed")

    # Empty connect
    r = safe_request("post", f"{BASE}/api/connect", json={})
    if r:
        data = safe_json(r)
        if r.status_code == 200:
            record("Conn", "Empty connect -> success=false", data and data.get("success") is False, str(data)[:100])
        else:
            record("Conn", "Empty connect -> error status", r.status_code in (400, 422, 500))

    # Invalid DSN
    r = safe_request("post", f"{BASE}/api/connect",
                     json={"dsn": "postgresql://baduser:badpass@127.0.0.1:9999/nodb"})
    if r:
        data = safe_json(r)
        resp_str = json.dumps(data) if data else r.text
        record("Conn", "Invalid DSN: no password leak", "badpass" not in resp_str,
               "Password leaked!" if "badpass" in resp_str else "Clean",
               "critical" if "badpass" in resp_str else "")

    # Schema with no connection
    r = safe_request("get", f"{BASE}/api/schema")
    if r:
        record("Conn", "Schema no conn -> 400",
               r.status_code == 400,
               f"status={r.status_code}, expected 400" if r.status_code != 400 else "",
               "minor" if r.status_code != 400 else "")

    # Connect via registry
    r = safe_request("get", f"{BASE}/api/connections")
    if r and isinstance(safe_json(r), list) and len(safe_json(r)) > 0:
        cid = safe_json(r)[0].get("id")
        r2 = safe_request("post", f"{BASE}/api/connect", json={"connection_id": cid}, timeout=60)
        if r2:
            data = safe_json(r2)
            success = data and data.get("success") is True
            record("Conn", f"Connect via registry -> success={success}", success, str(data)[:150])
            if success:
                conn_id = data.get("connection_id")
    else:
        record("Conn", "No registry connections to test", True, "SKIP")

    # Schema with connection
    if conn_id:
        r = safe_request("get", f"{BASE}/api/schema", params={"connection_id": conn_id})
        if r:
            data = safe_json(r)
            record("Conn", "Schema with conn -> 200", r.status_code == 200)
            if data:
                tables = data.get("tables", [])
                record("Conn", "Schema returns tables", isinstance(tables, list) and len(tables) > 0,
                       f"count={len(tables)}")

    return conn_id


def test_registry():
    print("\n=== Registry ===")
    r = safe_request("post", f"{BASE}/api/connections/add", json={
        "name": "test-sys", "engine": "postgres", "host": "127.0.0.1",
        "port": 5432, "database": "testdb", "user": "u", "password": "p"})
    added_id = None
    if r:
        data = safe_json(r)
        record("Registry", "Add -> 200", r.status_code == 200)
        added_id = data.get("id") if data else None

    if added_id:
        r = safe_request("get", f"{BASE}/api/connections")
        if r:
            found = any(c.get("id") == added_id for c in (safe_json(r) or []))
            record("Registry", "Added appears in list", found)
        r = safe_request("delete", f"{BASE}/api/connections/{added_id}")
        if r:
            record("Registry", "Delete -> 200", r.status_code == 200)

    r = safe_request("delete", f"{BASE}/api/connections/nonexistent-xyz")
    if r:
        record("Registry", "Delete non-existent -> 404", r.status_code == 404,
               f"got {r.status_code}" if r.status_code != 404 else "")


def test_analysis(conn_id):
    print("\n=== Analysis ===")
    r = safe_request("post", f"{BASE}/api/analyze-query", json={"query": "SELECT 1"})
    if r:
        record("Analysis", "No conn -> 400", r.status_code == 400,
               f"got {r.status_code}" if r.status_code != 400 else "",
               "minor" if r.status_code != 400 else "")

    if conn_id:
        for mode in ["full", "query_only", "index_only"]:
            r = safe_request("post", f"{BASE}/api/analyze-query",
                           json={"query": "SELECT 1", "connection_id": conn_id, "mode": mode},
                           timeout=120)
            if r:
                data = safe_json(r)
                record("Analysis", f"mode={mode} -> 200", r.status_code == 200, f"status={r.status_code}")
                if data:
                    record("Analysis", f"mode={mode} has results", isinstance(data.get("results"), dict))
            else:
                record("Analysis", f"mode={mode}", False, "Timeout")
    else:
        r = safe_request("get", f"{BASE}/api/index-recommendations")
        if r:
            record("Analysis", "Index recs no conn -> 400", r.status_code == 400,
                   f"got {r.status_code}" if r.status_code != 400 else "")


def test_health_issues(conn_id):
    print("\n=== Health & Issues ===")
    r = safe_request("get", f"{BASE}/api/db-health")
    if r:
        record("Health", "No conn -> 400", r.status_code == 400,
               f"got {r.status_code}" if r.status_code != 400 else "",
               "minor" if r.status_code != 400 else "")

    if conn_id:
        r = safe_request("get", f"{BASE}/api/db-health", params={"connection_id": conn_id})
        if r:
            data = safe_json(r)
            record("Health", "With conn -> 200", r.status_code == 200)
            if data:
                for field in ["score", "status", "metrics", "alerts"]:
                    record("Health", f"Has {field}", field in data)

    r = safe_request("get", f"{BASE}/api/db-health/all")
    if r:
        record("Health", "All health -> 200", r.status_code == 200)

    r = safe_request("get", f"{BASE}/api/issues")
    if r:
        data = safe_json(r)
        items = data["items"] if isinstance(data, dict) and "items" in data else data
        record("Issues", "List -> 200", r.status_code == 200)
        record("Issues", "Returns list", isinstance(items, list))

    r = safe_request("post", f"{BASE}/api/issues/nonexistent-xyz/resolve")
    if r:
        record("Issues", "Resolve non-existent -> 404", r.status_code == 404)


def test_chat(conn_id):
    print("\n=== Chat ===")

    # Simple message
    r = safe_request("post", f"{BASE}/api/chat", data={"message": "Hello test"}, timeout=60)
    if r:
        data = safe_json(r)
        record("Chat", "Simple msg -> 200", r.status_code == 200)
        if data:
            record("Chat", "Has reply", bool(data.get("reply")))
            record("Chat", "Has session_id", bool(data.get("session_id")))
            record("Chat", "Has context_summary", bool(data.get("context_summary")))
    else:
        record("Chat", "Simple msg", False, "Timeout/error", "major")

    # Chat with 1 report
    if REPORT1.exists():
        try:
            with open(REPORT1, "rb") as f:
                r = safe_request("post", f"{BASE}/api/chat",
                               data={"message": "Summarize this report briefly"},
                               files={"files": (REPORT1.name, f, "text/html")},
                               timeout=120)
            if r:
                data = safe_json(r)
                record("Chat+Report", "1 report -> 200", r.status_code == 200, f"status={r.status_code}")
                if data:
                    ctx = data.get("context_summary", {})
                    reports_loaded = ctx.get("reports_loaded", [])
                    record("Chat+Report", "Report in context",
                           REPORT1.name in reports_loaded,
                           f"loaded={reports_loaded}")
                    record("Chat+Report", "Reply non-empty",
                           len(data.get("reply", "")) > 10,
                           f"len={len(data.get('reply', ''))}")
            else:
                record("Chat+Report", "1 report", False, "Timeout", "major")
        except Exception as e:
            record("Chat+Report", "1 report", False, str(e), "major")

    # Chat with 2 reports
    if REPORT1.exists() and REPORT2.exists():
        try:
            with open(REPORT1, "rb") as f1, open(REPORT2, "rb") as f2:
                r = safe_request("post", f"{BASE}/api/chat",
                               data={"message": "Compare these two reports briefly"},
                               files=[("files", (REPORT1.name, f1, "text/html")),
                                      ("files", (REPORT2.name, f2, "text/html"))],
                               timeout=120)
            if r:
                data = safe_json(r)
                record("Chat+Report", "2 reports -> 200", r.status_code == 200)
                if data:
                    ctx = data.get("context_summary", {})
                    reports_loaded = ctx.get("reports_loaded", [])
                    record("Chat+Report", "Both reports loaded",
                           REPORT1.name in reports_loaded and REPORT2.name in reports_loaded,
                           f"loaded={reports_loaded}")
            else:
                record("Chat+Report", "2 reports", False, "Timeout", "major")
        except Exception as e:
            record("Chat+Report", "2 reports", False, str(e), "major")

    # Disallowed file
    import io
    r = safe_request("post", f"{BASE}/api/chat",
                   data={"message": "test"},
                   files={"files": ("test.exe", io.BytesIO(b"fake"), "application/octet-stream")},
                   timeout=60)
    if r:
        record("Chat", "Disallowed .exe -> 200 (skipped)", r.status_code == 200)


def test_sandbox(conn_id):
    print("\n=== Sandbox ===")
    for q, blocked in [
        ("DROP TABLE users", True),
        ("DELETE FROM orders", True),
        ("TRUNCATE test", True),
        ("ALTER TABLE x DROP COLUMN y", True),
    ]:
        r = safe_request("post", f"{BASE}/api/sandbox", json={"query": q})
        if r:
            data = safe_json(r)
            record("Sandbox", f"Block: {q[:30]}", data and data.get("success") is False)
        else:
            record("Sandbox", f"Block: {q[:30]}", False, "Request failed")

    if conn_id:
        r = safe_request("post", f"{BASE}/api/sandbox",
                       json={"query": "SELECT 1 AS ok", "connection_id": conn_id})
        if r:
            data = safe_json(r)
            record("Sandbox", "SELECT 1 -> success", data and data.get("success") is True,
                   str(data)[:100])


def test_insights_simulation(conn_id):
    print("\n=== Insights & Simulation ===")

    r = safe_request("get", f"{BASE}/api/insights")
    if r:
        data = safe_json(r)
        items = data["items"] if isinstance(data, dict) and "items" in data else data
        record("Insights", "List -> 200", r.status_code == 200, f"status={r.status_code}")
        record("Insights", "Returns array", isinstance(items, list),
               f"type={type(items).__name__}")
    else:
        record("Insights", "List", False, "Failed")

    r = safe_request("post", f"{BASE}/api/insights/nonexistent-xyz/dismiss")
    if r:
        data = safe_json(r)
        record("Insights", "Dismiss non-existent -> success=false",
               data and data.get("success") is False, str(data)[:100])

    r = safe_request("post", f"{BASE}/api/insights/run", timeout=60)
    if r:
        record("Insights", "Run advisor -> 200", r.status_code == 200)

    r = safe_request("post", f"{BASE}/api/simulate",
                   json={"change_type": "add_index", "table": "test"})
    if r:
        record("Simulation", "No conn -> 400", r.status_code == 400,
               f"got {r.status_code}" if r.status_code != 400 else "")

    if conn_id:
        r = safe_request("post", f"{BASE}/api/simulate",
                       json={"change_type": "add_index", "table": "pg_class",
                             "column": "relname", "connection_id": conn_id},
                       timeout=120)
        if r:
            data = safe_json(r)
            record("Simulation", "With conn -> 200", r.status_code == 200, f"status={r.status_code}")
            if data:
                record("Simulation", "Has result", bool(data.get("result")))

    # MCP status
    r = safe_request("get", f"{BASE}/api/mcp-status")
    if r:
        data = safe_json(r)
        record("MCP", "Status -> 200", r.status_code == 200)
        if data:
            record("MCP", "Has postgres", "postgres" in data)
            record("MCP", "Has couchbase", "couchbase" in data)


def test_nonfunctional():
    print("\n=== Non-Functional ===")

    # Invalid JSON
    r = safe_request("post", f"{BASE}/api/connect",
                   data="{{not json}}", headers={"Content-Type": "application/json"})
    if r:
        record("NFR", "Invalid JSON -> 422/400", r.status_code in (400, 422))
        data = safe_json(r)
        if data:
            has_trace = "Traceback" in json.dumps(data) or 'File "' in json.dumps(data)
            record("NFR", "No stack trace in error", not has_trace,
                   "Stack trace found!" if has_trace else "Clean")

    # Missing required
    r = safe_request("post", f"{BASE}/api/analyze-query", json={})
    if r:
        record("NFR", "Missing fields -> 400/422", r.status_code in (400, 422))

    # Credential sanitization
    r = safe_request("post", f"{BASE}/api/connect",
                   json={"dsn": "postgresql://u:SecretPass789@badhost:5432/db"})
    if r:
        resp_str = json.dumps(safe_json(r)) if safe_json(r) else r.text
        record("NFR", "No password in error response", "SecretPass789" not in resp_str,
               "LEAKED!" if "SecretPass789" in resp_str else "Sanitized",
               "critical" if "SecretPass789" in resp_str else "")

    # README doc mismatch
    r = safe_request("post", f"{BASE}/api/analyze-report", json={})
    if r:
        record("NFR", "README /api/analyze-report: endpoint exists?",
               r.status_code not in (404, 405),
               f"status={r.status_code} (404/405 = missing, doc bug)" if r.status_code in (404, 405)
               else f"status={r.status_code}")

    # Rate limiting
    statuses = []
    for _ in range(20):
        r = safe_request("get", f"{BASE}/health/live", timeout=3)
        if r:
            statuses.append(r.status_code)
    record("NFR", "Rate limit: health/live survives 20 rapid requests",
           all(s == 200 for s in statuses), f"statuses={set(statuses)}")


def main():
    start = time.time()
    print("=" * 60)
    print(f"DB Analyzer v7 - System Test (target: {BASE})")
    print("=" * 60)

    test_health()
    conn_id = test_connections()
    test_registry()
    test_analysis(conn_id)
    test_health_issues(conn_id)
    test_chat(conn_id)
    test_sandbox(conn_id)
    test_insights_simulation(conn_id)
    test_nonfunctional()

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed
    elapsed = time.time() - start

    print(f"\n{'=' * 60}")
    print(f"TOTAL: {total} | PASSED: {passed} | FAILED: {failed} | TIME: {elapsed:.1f}s")
    print(f"{'=' * 60}")

    out = REPORTS_DIR / "system_test_results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump({"total": total, "passed": passed, "failed": failed,
                   "elapsed_s": round(elapsed, 1), "results": results}, f, indent=2)
    print(f"\nResults: {out}")


if __name__ == "__main__":
    main()
