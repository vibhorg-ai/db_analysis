# Hardcoded Values Report (v7)

All detected hardcoded values in the project. **No values were modified** — this is a report only.  
Excludes third-party code (e.g. `node_modules/`).

---

## 1. URLs, hosts, and ports

| File | Line | Value / expression | Notes |
|------|------|--------------------|--------|
| backend/core/config.py | 24 | `"127.0.0.1"` | Default app host |
| backend/core/config.py | 25 | `8004` | Default app port |
| backend/api/app.py | 324 | `["https://tracewise-ui:8443"]` | CORS extra origin |
| backend/connectors/couchbase_connector.py | 155 | `"couchbase://localhost"` | Default connection string fallback |
| backend/connectors/postgres_connector.py | 52 | `"localhost"` | Default host in DSN |
| backend/core/db_registry.py | 79–80 | `"localhost"`, `5432` | Default host/port in DSN property |
| backend/api/routes.py | 137–138 | `"localhost"`, `5432` | Default host/port for connect |
| tests/api_test_battery.py | 4 | `http://127.0.0.1:8004` | Test base URL (docstring) |
| tests/system_test_runner.py | 4 | `http://127.0.0.1:8004` | Docstring |
| tests/system_test_runner.py | 17 | `"http://127.0.0.1:8010"` | Default TEST_BASE_URL |
| tests/system_test_runner.py | 679 | `"ws://127.0.0.1:8004/ws"` | WebSocket URL |
| tests/system_test_quick.py | 14 | `"http://127.0.0.1:8010"` | Default TEST_BASE_URL |
| tests/run_all_tests.py | 14 | `"http://127.0.0.1:8010"` | Default TEST_BASE_URL |
| tests/e2e/app.spec.ts | 59 | `"http://localhost:3000"` | Default BASE_URL |
| tests/e2e/playwright.config.ts | 16 | `"http://localhost:3000"` | Default baseURL |
| tests/e2e/README.md | 7–10, 23 | 8004, 3000, localhost | Docs |
| tests/conftest.py | 119 | `"http://test"` | Test client base_url |
| tests/test_api.py | 15+ | `"http://test"` | AsyncClient base_url (multiple) |
| docker/docker-compose.yml | 7–9, 16–17, 33, 46 | 8004, 9080, 9443, 443, 80 | Ports and comments |
| docker/README.md | 54–56 | 8004, 9080, 9443 | Port table |
| docker/check-api-endpoints.ps1 | 1, 5 | `https://db-analyzer:9443` | Base URL for checks |
| docker/traefik/generate-certs.ps1 | 41–42 | `localhost`, `127.0.0.1` | SANs |
| docker/traefik/generate-certs.sh | 40–41 | `localhost`, `127.0.0.1` | SANs |
| frontend/vite.config.ts | 7, 9–12 | `3000`, `https://db-analyzer:9443`, `wss://db-analyzer:9443` | Dev server port and proxy targets |
| frontend/src/pages/ConnectionsPage.tsx | 23, 209, 213, 235 | `"5432"`, `"localhost"`, `"couchbase://localhost"` | Form defaults/placeholders |
| README.md | 37, 45 | 127.0.0.1:8004, localhost:3000, 8004 | Docs |
| .env.example | 7–8 | 0.0.0.0, 8004 | App host/port |

---

## 2. Database and connection strings

| File | Line | Value / expression | Notes |
|------|------|--------------------|--------|
| backend/core/config.py | 47 | `"couchbase://localhost"` | Default Couchbase connection string |
| backend/connectors/couchbase_connector.py | 68, 72, 75 | `"couchbase://"`, `"couchbases://"`, `f"couchbase://{raw}"` | Scheme handling |
| backend/api/routes.py | 84–86, 142 | postgresql redaction pattern; `f"postgresql://{user}:..."` | DSN building |
| backend/core/db_registry.py | 76, 84 | `"postgresql://..."` template | DSN property |
| tests/test_connectors.py | 65, 72, 77, 91, 113–114 | `"postgresql://user:pass@localhost/db"`, `:5432/testdb` | Test DSNs |
| tests/system_test_runner.py | 119, 195–196, 649 | postgresql DSNs with 127.0.0.1, 9999, 5432 | Test payloads |
| tests/system_test_quick.py | 89, 136–137, 384 | postgresql DSNs | Test payloads |
| tests/run_all_tests.py | 89, 413 | postgresql DSNs | Test payloads |
| db_connections.yaml | 6, 15 | `5432` | Port in YAML |
| .env | (sample) | POSTGRES_DSN, COUCHBASE_*, MCP_* | Actual credentials (do not commit); listed here as “value present” |

---

## 3. Paths and file/directory names

| File | Line | Value / expression | Notes |
|------|------|--------------------|--------|
| backend/core/config.py | 38–41 | `"prompts"`, `"reports"`, `"data"`, `"memory"` | Default dir names |
| backend/core/config.py | 46 | `"db_connections.yaml"` | Registry file name |
| backend/core/db_registry.py | (uses settings) | data_dir, db_connections_file | Resolved under _V7_ROOT |
| backend/agents/learning_agent.py | 19 | `... / "memory"` | Memory dir under project root |
| backend/core/report_parser.py | 230 | `"data"` (key in section) | JSON key, not path |
| tests/*.py | various | `"reports"`, `reports/` | REPORTS_DIR, output paths |
| .env.example | 21–24 | PROMPTS_DIR=prompts, etc. | Path env vars |
| Dockerfile | 24 | `data memory reports` | mkdir dirs |

---

## 4. Magic numbers and timeouts

| File | Line | Value | Notes |
|------|------|--------|--------|
| backend/core/config.py | 32 | `600` | HTTPX_REQUEST_TIMEOUT |
| backend/core/config.py | 45 | `30` | db_connect_timeout |
| backend/core/config.py | 68 | `50` | body_size_limit_mib |
| backend/core/config.py | 71 | `300` | schema_cache_ttl_seconds |
| backend/core/config.py | 77 | `16000` | llm_max_context_tokens |
| backend/core/config.py | 80–81 | `90`, `5` | pipeline_stage_timeout, pipeline_max_concurrency |
| backend/core/config.py | 85 | `60` | circuit_breaker_seconds |
| backend/api/app.py | 133–140, 315–316 | `100`, `60.0` | Rate limit: 100 req / 60s per IP |
| backend/api/routes.py | 789, 1179 | `500` | Max limit for issues/insights pagination |
| backend/api/routes.py | 984, 987 | `20 * 1024 * 1024`, "20 MB limit" | File upload size |
| backend/api/routes.py | 1035 | `50_000` | MAX_QUERY_LENGTH (sandbox) |
| backend/api/routes.py | 1095 | `30.0` | _SANDBOX_TIMEOUT |
| backend/connectors/couchbase_connector.py | 24–25 | `30`, `30` | DEFAULT_QUERY_TIMEOUT, DEFAULT_MANAGEMENT_TIMEOUT |
| backend/connectors/couchbase_connector.py | 287 | `5` | QueryOptions timeout seconds |
| backend/connectors/couchbase_connector.py | 314 | `50_000` | max_rows |
| backend/connectors/postgres_connector.py | 132, 141 | `30.0` | timeout default |
| backend/core/metrics.py | 32 | `1000` | _MAX_DURATION_SAMPLES |
| backend/core/report_parser.py | 21, 23 | `50`, `30` | _MAX_TABLE_ROWS, _MAX_DATASET_ROWS |
| backend/core/report_parser.py | 213, 227 | `20` | Section/row slicing |
| backend/core/chat_session.py | 31–32 | `20_000`, `50` | MAX_SCHEMA_CONTEXT_CHARS, MAX_HISTORY_MESSAGES |
| backend/core/chat_session.py | 87 | `20000` | max_tokens default |
| backend/core/chat_session.py | 160–161 | `5000` | Summary truncation |
| backend/core/chat_session.py | 209 | `500` | MAX_SESSIONS |
| backend/core/llm_router.py | 30 | `[5, 10, 15]` | RETRY_BACKOFF |
| backend/time_travel/issue_history.py | 27 | `5000` | MAX_ISSUES |
| backend/time_travel/query_history.py | 43, 50–51 | `100`, `1000`, `50` | get_history/slow_queries limits |
| backend/time_travel/schema_history.py | 82 | `50` | get_history limit |
| backend/time_travel/performance_history.py | 20, 44 | `1000`, `100` | max_snapshots, get_history limit |
| backend/scheduler/advisor_job.py | 44, 46 | ADVISOR_INTERVAL_MINUTES*60, `30` | interval and sleep |
| backend/scheduler/monitoring_job.py | 72 | monitoring_interval_minutes * 60 | interval |
| backend/intelligence/* (multiple) | various | 50, 100, 90, 60, 5, 30, 1000, 5000, 20, 300, etc. | Confidence, limits, thresholds |
| backend/core/health_monitor.py | 105, 111, 159–160, 167, 170, 182, 184, 200, 204, 214, 241, 252, 256 | 30, 5, 0–100, weights 30/15/15, 5, 90, 80, 50 | Health scoring weights and thresholds |
| backend/core/prompt_trim.py | 73, 80 | `500`, `500` | Truncation and reserved_chars |
| backend/agents/learning_agent.py | 28, 58–59, 62 | 500, 500, 20 | Truncation and limits |
| backend/agents/time_travel_agent.py | 34, 37–43, 59, 73, 87 | 20, 50, 1000, 30, 50, 500 | History and description truncation |
| backend/graph/entity_graph.py | 93 | `0.5`, `0.3` | Score weights |
| Dockerfile | 6 | `1024` | ENV HTTPX_REQUEST_TIMEOUT (overrides config) |
| Dockerfile | 28 | `8004` | EXPOSE and CMD port |
| tests/test_report_parser.py | 184–185, 188–189 | `3000` | Char truncation in test output |

---

## 5. Flow names, keys, and service identifiers

| File | Line | Value | Notes |
|------|------|--------|--------|
| backend/core/config.py | 39–42 | AMAIZ_CHAT_FLOW_NAME, AMAIZ_FLOW_NAME, AMAIZ_CONTEXT_KEY | `"chat"`, `"db_analysis_amaiz_pipeline"`, `"context_data"` (defaults) |
| backend/api/app.py | 324 | `"https://tracewise-ui:8443"` | CORS extra origin (service name) |
| frontend/vite.config.ts | 9–12 | `db-analyzer:9443` | Proxy hostname |
| docker/check-api-endpoints.ps1 | 5 | `db-analyzer:9443` | Host in URL |
| docker/docker-compose.yml | 42 | `db-analyzer` | Traefik Host rule |

---

## 6. Other literals

| File | Line | Value | Notes |
|------|------|--------|--------|
| backend/core/config.py | 69 | `"*"` | cors_allowed_origins default |
| backend/api/app.py | 34, 41 | Redaction patterns for password, api_key, secret, token, postgresql | Log filter |
| backend/core/db_registry.py | 53 | UUID digest slice indices `[:8]`, `[8:12]`, etc. | Deterministic ID format |
| tests/test_connectors.py | 72 | `"postgresql://nonexistent/db"` | Cache key in test |
| docker/Dockerfile | 9–10 | Commented proxy env (10.232.233.70:8080, no_proxy list) | Corporate proxy; commented |
| .env.example | 50 | `*` | CORS default |

---

## Summary

- **URLs/ports**: Default app (127.0.0.1:8004), test bases (127.0.0.1:8010, localhost:3000), Docker (8004, 9080, 9443), CORS origin (tracewise-ui:8443), frontend proxy (db-analyzer:9443).
- **DB**: Default Couchbase `couchbase://localhost`; Postgres default port 5432 and host localhost in several places.
- **Paths**: prompts, reports, data, memory, db_connections.yaml (and custom_connections.yaml under data_dir).
- **Magic numbers**: Rate limit 100/60; timeouts 30, 90, 600, 1024; limits 500, 5000, 50_000, 20_000; health weights and thresholds; many limits in intelligence and time_travel.
- **Secrets**: Actual credentials only in `.env` (not in repo); test DSNs use dummy credentials.

Recommendation: Move configurable defaults into `Settings` or `.env.example` and document; keep test-only literals in tests but consider env or constants for base URLs/ports.
