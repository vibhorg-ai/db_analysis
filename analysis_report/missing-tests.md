# Static Analysis — Missing Tests (v7)

Modules or areas that lack dedicated or sufficient test coverage.

---

## Backend — No dedicated tests

These modules have no corresponding `test_*.py` or are only lightly covered by system/integration tests:

| Module / area | Path | Notes |
|---------------|------|--------|
| Core config | `backend/core/config.py` | No tests for `_find_env_file`, `get_settings()`, or env loading. |
| Core auth | `backend/core/auth.py` | Keycloak and API-key logic not unit-tested. |
| Core metrics | `backend/core/metrics.py` | No tests for counters and Prometheus output. |
| Core instance_id | `backend/core/instance_id.py` | Trivial but untested. |
| Core schema_cache | `backend/core/schema_cache.py` | Cache get/set/invalidation not tested. |
| Core connection_manager | `backend/core/connection_manager.py` | Connection lifecycle and snapshot not tested. |
| Core db_registry | `backend/core/db_registry.py` | YAML loading and DSN building not unit-tested. |
| Core health_monitor | `backend/core/health_monitor.py` | Scoring and metric collection not tested. |
| Core chat_session | `backend/core/chat_session.py` | Session build and message trimming not tested. |
| Core prompt_trim | `backend/core/prompt_trim.py` | Token trimming logic not tested. |
| Core circuit_breaker | `backend/core/circuit_breaker.py` | Open/close/half-open logic not tested. |
| Core agent_router | `backend/core/agent_router.py` | Routing logic not tested. |
| Core amaiz_service | `backend/core/amaiz_service.py` | AMAIZ client calls not mocked/tested. |
| Core llm_router | `backend/core/llm_router.py` | Retry and session logic not tested. |
| API app | `backend/api/app.py` | Middleware (rate limit, CORS, body size, API key) not unit-tested. |
| API websocket | `backend/api/websocket.py` | WebSocket message handling not tested. |
| Connectors base | `backend/connectors/base.py` | Protocol/ABC not tested. |
| Connectors couchbase | `backend/connectors/couchbase_connector.py` | Only postgres covered in test_connectors; Couchbase untested. |
| Connectors mcp_adapter | `backend/connectors/mcp_adapter.py` | Not tested. |
| MCP bridge | `backend/mcp/bridge.py` | Config stripping and sync not tested. |
| Scheduler monitoring_job | `backend/scheduler/monitoring_job.py` | Not tested. |
| Scheduler advisor_job | `backend/scheduler/advisor_job.py` | Not tested. |
| Time travel | `backend/time_travel/*.py` | No tests. |
| Graph | `backend/graph/*.py` | No unit tests. |
| Intelligence simulation_engine | `backend/intelligence/simulation_engine/*.py` | No unit tests. |
| Intelligence autonomous_advisor | `backend/intelligence/autonomous_advisor/*.py` | No unit tests. |
| Agents (individual) | `backend/agents/*.py` (except covered by test_agents) | Many agents not individually tested; only test_agents.py exists. |

---

## Backend — Partially covered

| Module | Existing tests | Gaps |
|--------|----------------|------|
| API routes | `tests/test_api.py` | Only a subset of endpoints; no tests for chat upload, sandbox, simulation, MCP, insights. |
| Connectors | `tests/test_connectors.py` | Postgres connector only; no Couchbase. |
| Report parser | `tests/test_report_parser.py` | Likely covers main parsing; edge cases and malformed HTML may be missing. |
| Agents | `tests/test_agents.py` | Coverage of orchestrator/agents may be partial; per-agent behavior not fully tested. |

---

## Frontend

- No unit tests (e.g. Vitest/Jest) for React components, hooks, or API client.
- E2E tests in `tests/e2e/` cover basic navigation and flows but not all pages or error paths.

---

## System / E2E

- `tests/system_test_runner.py` and `tests/run_all_tests.py` require a running server and optional report files; not runnable in CI without environment.
- No automated CI job definition (e.g. GitHub Actions) to run pytest and system tests against a started app.

---

## Summary

- **Backend**: ~4 test files for ~68 backend modules; most of `core/`, `connectors/`, `agents/`, `intelligence/`, `graph/`, `scheduler/`, `mcp/`, `time_travel/` have no dedicated unit tests.
- **Frontend**: No unit tests.
- **E2E/System**: Present but not wired to a standard CI pipeline with a documented test environment.

Recommendation: Add unit tests for `config`, `auth`, `report_parser`, `chat_session`, `health_monitor`, `db_registry`, and one agent/orchestrator path first; then expand to connectors and intelligence modules.
