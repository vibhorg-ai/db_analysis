#!/usr/bin/env python3
"""System test runner with full error handling."""
import sys
import json
import os
import io
import time
from pathlib import Path

sys.stdout.reconfigure(line_buffering=True)

import requests

BASE = os.environ.get("TEST_BASE_URL", "http://127.0.0.1:8010")
REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "reports"
REPORT1 = REPORTS_DIR / "PGAWR_13558_13559_172.24.202.145_EXTENDED.html"
REPORT2 = REPORTS_DIR / "PGAWR_13560_13561_172.24.202.145_EXTENDED.html"

results = []

def t(area, test, passed, detail="", sev=""):
    results.append({"area": area, "test": test, "passed": passed, "detail": detail, "severity": sev})
    s = "PASS" if passed else "FAIL"
    extra = f" -- {detail[:120]}" if detail and not passed else ""
    print(f"  [{s}] {area}: {test}{extra}", flush=True)

def sj(r):
    try:
        return r.json()
    except Exception:
        return None

def GET(url, **kw):
    kw.setdefault("timeout", 15)
    return requests.get(url, **kw)

def POST(url, **kw):
    kw.setdefault("timeout", 15)
    return requests.post(url, **kw)

print(f"Target: {BASE}", flush=True)
start_time = time.time()

# ============ Health ============
print("\n=== Health & Infra ===", flush=True)
try:
    r = GET(f"{BASE}/health/live")
    t("Health", "/health/live 200", r.status_code == 200)
    t("Health", "status=ok", sj(r) and sj(r).get("status") == "ok")
except Exception as e:
    t("Health", "/health/live", False, str(e), "critical")

try:
    r = GET(f"{BASE}/health/ready")
    t("Health", "/health/ready 200", r.status_code == 200)
    t("Health", "has version", sj(r) and "version" in sj(r))
except Exception as e:
    t("Health", "/health/ready", False, str(e))

try:
    r = GET(f"{BASE}/metrics")
    t("Health", "/metrics 200", r.status_code == 200)
    t("Health", "text/plain", "text/plain" in r.headers.get("content-type", ""))
except Exception as e:
    t("Health", "/metrics", False, str(e))

# ============ Connections ============
print("\n=== Connections ===", flush=True)
try:
    r = GET(f"{BASE}/api/connections")
    d = sj(r)
    t("Conn", "list 200", r.status_code == 200)
    t("Conn", "returns list", isinstance(d, list), f"count={len(d) if isinstance(d, list) else 'N/A'}")
except Exception as e:
    t("Conn", "list", False, str(e))

try:
    r = POST(f"{BASE}/api/connect", json={}, timeout=25)
    d = sj(r)
    if r.status_code == 200:
        t("Conn", "empty connect fail", d and d.get("success") is False)
    else:
        t("Conn", "empty connect error", r.status_code in (400, 422, 500))
except Exception as e:
    t("Conn", "empty connect", False, str(e))

try:
    r = POST(f"{BASE}/api/connect",
             json={"dsn": "postgresql://u:MySecret99@127.0.0.1:9999/x"}, timeout=25)
    d = sj(r)
    resp = json.dumps(d) if d else r.text
    leaked = "MySecret99" in resp
    t("Conn", "no pwd leak in error", not leaked,
      "LEAKED!" if leaked else "OK", "critical" if leaked else "")
except Exception as e:
    t("Conn", "pwd leak test", False, str(e))

try:
    r = GET(f"{BASE}/api/schema", timeout=10)
    t("Conn", "schema no conn -> 400", r.status_code == 400,
      f"got {r.status_code}" if r.status_code != 400 else "", "minor" if r.status_code != 400 else "")
except requests.Timeout:
    t("Conn", "schema no conn -> 400", False, "TIMEOUT: hangs instead of returning 400", "major")
except Exception as e:
    t("Conn", "schema no conn", False, str(e))

# Connect via registry
conn_id = None
try:
    r = GET(f"{BASE}/api/connections")
    conns = sj(r) or []
    if conns:
        cid = conns[0]["id"]
        print(f"  Connecting registry id={cid}...", flush=True)
        r2 = POST(f"{BASE}/api/connect", json={"connection_id": cid}, timeout=60)
        d2 = sj(r2)
        ok = d2 and d2.get("success")
        t("Conn", "registry connect", ok, str(d2)[:120])
        if ok:
            conn_id = d2.get("connection_id")
    else:
        t("Conn", "no registry connections", True, "SKIP")
except Exception as e:
    t("Conn", "registry connect", False, str(e))

# Schema with connection
if conn_id:
    try:
        r = GET(f"{BASE}/api/schema", params={"connection_id": conn_id}, timeout=30)
        d = sj(r)
        t("Conn", "schema with conn -> 200", r.status_code == 200)
        if d:
            tables = d.get("tables", [])
            t("Conn", "schema has tables", isinstance(tables, list) and len(tables) > 0,
              f"count={len(tables) if isinstance(tables, list) else 'N/A'}")
    except Exception as e:
        t("Conn", "schema with conn", False, str(e))

# ============ Registry ============
print("\n=== Registry ===", flush=True)
aid = None
try:
    r = POST(f"{BASE}/api/connections/add",
             json={"name": "sys-test", "engine": "postgres",
                   "host": "x", "port": 5432, "database": "d",
                   "user": "u", "password": "p"})
    d = sj(r)
    t("Registry", "add -> 200", r.status_code == 200)
    aid = d.get("id") if d else None
except Exception as e:
    t("Registry", "add", False, str(e))

if aid:
    try:
        r = GET(f"{BASE}/api/connections")
        found = any(c.get("id") == aid for c in (sj(r) or []))
        t("Registry", "appears in list", found)
    except Exception as e:
        t("Registry", "appears in list", False, str(e))
    try:
        r = requests.delete(f"{BASE}/api/connections/{aid}", timeout=10)
        t("Registry", "delete -> 200", r.status_code == 200)
    except Exception as e:
        t("Registry", "delete", False, str(e))

try:
    r = requests.delete(f"{BASE}/api/connections/nonexistent", timeout=10)
    t("Registry", "delete nonexist -> 404", r.status_code == 404, f"got {r.status_code}")
except Exception as e:
    t("Registry", "delete nonexist", False, str(e))

# ============ Analysis ============
print("\n=== Analysis ===", flush=True)
try:
    r = POST(f"{BASE}/api/analyze-query", json={"query": "SELECT 1"}, timeout=10)
    t("Analysis", "no conn -> 400", r.status_code == 400,
      f"got {r.status_code}" if r.status_code != 400 else "",
      "minor" if r.status_code != 400 else "")
except requests.Timeout:
    t("Analysis", "no conn", False, "TIMEOUT: hangs instead of 400", "major")
except Exception as e:
    t("Analysis", "no conn", False, str(e))

if conn_id:
    for mode in ["full", "query_only", "index_only"]:
        print(f"  analyze mode={mode}...", flush=True)
        try:
            r = POST(f"{BASE}/api/analyze-query",
                     json={"query": "SELECT 1", "connection_id": conn_id, "mode": mode},
                     timeout=120)
            d = sj(r)
            t("Analysis", f"{mode} -> 200", r.status_code == 200)
            if d:
                t("Analysis", f"{mode} has results", isinstance(d.get("results"), dict),
                  f"keys={list(d.get('results', {}).keys())[:5]}")
        except requests.Timeout:
            t("Analysis", f"{mode}", False, "Timeout 120s", "major")
        except Exception as e:
            t("Analysis", f"{mode}", False, str(e))

# ============ Health & Issues ============
print("\n=== Health & Issues ===", flush=True)
try:
    r = GET(f"{BASE}/api/db-health", timeout=10)
    t("DB Health", "no conn -> 400", r.status_code == 400,
      f"got {r.status_code}" if r.status_code != 400 else "",
      "minor" if r.status_code != 400 else "")
except requests.Timeout:
    t("DB Health", "no conn", False, "TIMEOUT: hangs instead of 400", "major")
except Exception as e:
    t("DB Health", "no conn", False, str(e))

if conn_id:
    try:
        r = GET(f"{BASE}/api/db-health", params={"connection_id": conn_id}, timeout=20)
        d = sj(r)
        t("DB Health", "with conn -> 200", r.status_code == 200)
        if d:
            for field in ["score", "status", "metrics", "alerts"]:
                t("DB Health", f"has {field}", field in d)
    except Exception as e:
        t("DB Health", "with conn", False, str(e))

try:
    r = GET(f"{BASE}/api/db-health/all", timeout=20)
    t("DB Health", "all -> 200", r.status_code == 200)
except Exception as e:
    t("DB Health", "all", False, str(e))

try:
    r = GET(f"{BASE}/api/issues")
    d = sj(r)
    items = d["items"] if isinstance(d, dict) and "items" in d else d
    t("Issues", "list -> 200", r.status_code == 200)
    t("Issues", "returns list", isinstance(items, list))
except Exception as e:
    t("Issues", "list", False, str(e))

try:
    r = POST(f"{BASE}/api/issues/nonexistent/resolve")
    t("Issues", "resolve nonexist -> 404", r.status_code == 404)
except Exception as e:
    t("Issues", "resolve nonexist", False, str(e))

# ============ Chat ============
print("\n=== Chat ===", flush=True)
print("  simple message...", flush=True)
try:
    r = POST(f"{BASE}/api/chat", data={"message": "Hello"}, timeout=120)
    d = sj(r)
    t("Chat", "simple msg -> 200", r.status_code == 200)
    if d:
        t("Chat", "has reply", bool(d.get("reply")), f"len={len(d.get('reply', ''))}")
        t("Chat", "has session_id", bool(d.get("session_id")))
        t("Chat", "has context_summary", bool(d.get("context_summary")))
except requests.Timeout:
    t("Chat", "simple msg", False, "Timeout 120s", "major")
except Exception as e:
    t("Chat", "simple msg", False, str(e), "major")

print("  1 report...", flush=True)
if REPORT1.exists():
    try:
        with open(REPORT1, "rb") as f:
            r = POST(f"{BASE}/api/chat",
                     data={"message": "Summarize report"},
                     files={"files": (REPORT1.name, f, "text/html")},
                     timeout=180)
        d = sj(r)
        t("Chat+Report", "1 report -> 200", r.status_code == 200, f"status={r.status_code}")
        if d:
            ctx = d.get("context_summary", {})
            reps = ctx.get("reports_loaded", [])
            t("Chat+Report", "report in context", REPORT1.name in reps, f"loaded={reps}")
            t("Chat+Report", "reply non-empty", len(d.get("reply", "")) > 10)
    except requests.Timeout:
        t("Chat+Report", "1 report", False, "Timeout 180s", "major")
    except Exception as e:
        t("Chat+Report", "1 report", False, str(e), "major")

print("  2 reports...", flush=True)
if REPORT1.exists() and REPORT2.exists():
    try:
        with open(REPORT1, "rb") as f1, open(REPORT2, "rb") as f2:
            r = POST(f"{BASE}/api/chat",
                     data={"message": "Compare these reports"},
                     files=[("files", (REPORT1.name, f1, "text/html")),
                            ("files", (REPORT2.name, f2, "text/html"))],
                     timeout=180)
        d = sj(r)
        t("Chat+Report", "2 reports -> 200", r.status_code == 200)
        if d:
            ctx = d.get("context_summary", {})
            reps = ctx.get("reports_loaded", [])
            t("Chat+Report", "both reports loaded",
              REPORT1.name in reps and REPORT2.name in reps, f"loaded={reps}")
            reply = d.get("reply", "")
            t("Chat+Report", "comparison reply", len(reply) > 50, f"len={len(reply)}")
    except requests.Timeout:
        t("Chat+Report", "2 reports", False, "Timeout 180s", "major")
    except Exception as e:
        t("Chat+Report", "2 reports", False, str(e), "major")

print("  disallowed file...", flush=True)
try:
    r = POST(f"{BASE}/api/chat",
             data={"message": "test"},
             files={"files": ("test.exe", io.BytesIO(b"fake"), "application/octet-stream")},
             timeout=120)
    t("Chat", "disallowed .exe -> 200", r.status_code == 200)
except requests.Timeout:
    t("Chat", "disallowed .exe", False, "Timeout", "major")
except Exception as e:
    t("Chat", "disallowed .exe", False, str(e))

# ============ Sandbox ============
print("\n=== Sandbox ===", flush=True)
for q in ["DROP TABLE x", "DELETE FROM x", "TRUNCATE x", "ALTER TABLE x DROP COLUMN y"]:
    try:
        r = POST(f"{BASE}/api/sandbox", json={"query": q})
        d = sj(r)
        t("Sandbox", f"blocked: {q[:25]}", d and d.get("success") is False)
    except Exception as e:
        t("Sandbox", f"blocked: {q[:25]}", False, str(e))

if conn_id:
    try:
        r = POST(f"{BASE}/api/sandbox",
                 json={"query": "SELECT 1 AS ok", "connection_id": conn_id}, timeout=20)
        d = sj(r)
        t("Sandbox", "SELECT 1 ok", d and d.get("success") is True, str(d)[:100])
    except Exception as e:
        t("Sandbox", "SELECT 1", False, str(e))

# ============ Insights & Simulation ============
print("\n=== Insights & Simulation ===", flush=True)
try:
    r = GET(f"{BASE}/api/insights")
    d = sj(r)
    items = d["items"] if isinstance(d, dict) and "items" in d else d
    t("Insights", "list -> 200", r.status_code == 200, f"status={r.status_code}")
    t("Insights", "returns array", isinstance(items, list))
except Exception as e:
    t("Insights", "list", False, str(e))

try:
    r = POST(f"{BASE}/api/insights/nonexistent/dismiss")
    d = sj(r)
    t("Insights", "dismiss nonexist -> false", d and d.get("success") is False)
except Exception as e:
    t("Insights", "dismiss", False, str(e))

try:
    print("  running advisor...", flush=True)
    r = POST(f"{BASE}/api/insights/run", timeout=60)
    t("Insights", "run -> 200", r.status_code == 200)
except Exception as e:
    t("Insights", "run", False, str(e))

try:
    r = POST(f"{BASE}/api/simulate",
             json={"change_type": "add_index", "table": "t"})
    t("Simulation", "no conn -> 400", r.status_code == 400,
      f"got {r.status_code}" if r.status_code != 400 else "")
except Exception as e:
    t("Simulation", "no conn", False, str(e))

if conn_id:
    try:
        print("  running simulation...", flush=True)
        r = POST(f"{BASE}/api/simulate",
                 json={"change_type": "add_index", "table": "pg_class",
                       "column": "relname", "connection_id": conn_id}, timeout=120)
        d = sj(r)
        t("Simulation", "with conn -> 200", r.status_code == 200, f"status={r.status_code}")
        if d:
            t("Simulation", "has result", bool(d.get("result")))
    except requests.Timeout:
        t("Simulation", "with conn", False, "Timeout", "major")
    except Exception as e:
        t("Simulation", "with conn", False, str(e))

# ============ MCP ============
print("\n=== MCP ===", flush=True)
try:
    r = GET(f"{BASE}/api/mcp-status")
    d = sj(r)
    t("MCP", "status -> 200", r.status_code == 200)
    t("MCP", "has postgres", d and "postgres" in d)
    t("MCP", "has couchbase", d and "couchbase" in d)
except Exception as e:
    t("MCP", "status", False, str(e))

# ============ NFR ============
print("\n=== Non-Functional ===", flush=True)
try:
    r = POST(f"{BASE}/api/connect",
             data="not json", headers={"Content-Type": "application/json"})
    t("NFR", "invalid json -> 422", r.status_code in (400, 422))
    d = sj(r)
    if d:
        has_trace = "Traceback" in json.dumps(d) or 'File "' in json.dumps(d)
        t("NFR", "no stack trace", not has_trace, "Stack trace found!" if has_trace else "Clean")
except Exception as e:
    t("NFR", "invalid json", False, str(e))

try:
    r = POST(f"{BASE}/api/analyze-query", json={})
    t("NFR", "missing fields -> 422", r.status_code in (400, 422))
except Exception as e:
    t("NFR", "missing fields", False, str(e))

try:
    r = POST(f"{BASE}/api/connect",
             json={"dsn": "postgresql://u:SecretXYZ@bad:5432/d"}, timeout=25)
    resp = json.dumps(sj(r)) if sj(r) else r.text
    t("NFR", "pwd sanitization", "SecretXYZ" not in resp,
      "LEAKED!" if "SecretXYZ" in resp else "OK",
      "critical" if "SecretXYZ" in resp else "")
except Exception as e:
    t("NFR", "pwd sanitization", False, str(e))

try:
    r = POST(f"{BASE}/api/analyze-report", json={})
    t("NFR", "/api/analyze-report doc bug",
      r.status_code in (404, 405),
      f"status={r.status_code} (missing endpoint, README says it exists)", "minor")
except Exception as e:
    t("NFR", "/api/analyze-report", False, str(e))

# ============ Summary ============
total = len(results)
passed = sum(1 for x in results if x["passed"])
failed = total - passed
elapsed = time.time() - start_time

print(f"\n{'='*60}", flush=True)
print(f"TOTAL: {total} | PASSED: {passed} | FAILED: {failed} | TIME: {elapsed:.1f}s", flush=True)
print(f"{'='*60}", flush=True)

out = Path(__file__).resolve().parent.parent / "reports" / "system_test_results.json"
with open(out, "w") as f:
    json.dump({"total": total, "passed": passed, "failed": failed,
               "elapsed_s": round(elapsed, 1), "results": results}, f, indent=2)
print(f"Written to {out}", flush=True)
