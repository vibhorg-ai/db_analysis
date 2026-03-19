# Static Analysis — Issues (v7)

All detected problems grouped by category. **Report only** — no functionality was changed.

---

## Code smells

- **Broad exception handling**: Many handlers catch `Exception` without re-raising or logging (e.g. `backend/api/routes.py`, `backend/core/db_registry.py`, `backend/connectors/couchbase_connector.py`, `backend/core/amaiz_service.py`, `backend/api/websocket.py`, `backend/agents/learning_agent.py`). This can hide bugs and make debugging hard.
- **Duplicate `get_settings()` calls**: Routes and app code call `get_settings()` repeatedly in the same request path instead of injecting or caching per-request.
- **Magic strings**: Engine names `"postgres"` and `"couchbase"` appear as literals in many places; should be constants or an enum.
- **Large route module**: `backend/api/routes.py` is very long (~1300 lines); multiple responsibilities (connect, schema, health, chat, sandbox, issues, insights, simulation, MCP) could be split into sub-routers.
- **Global mutable state**: `_orchestrator`, `_llm_router`, `_connections_lock`, `_active_connections` are module-level globals; complicates testing and concurrency reasoning.

---

## Architecture

- **Tight coupling to AMAIZ**: LLM and pipeline logic is tied to AMAIZ; no abstraction for swapping providers.
- **In-memory session store**: Chat sessions are in-memory only; restart loses all sessions and no persistence option.
- **Mixed sync/async**: Some code paths mix sync and async (e.g. sync `get_settings()` in async route handlers); no clear boundary.
- **No clear domain layer**: Business logic is spread across routes, agents, and core; no dedicated domain/service layer for key flows.

---

## Anti-patterns

- **Bare `except Exception`**: Several places catch `Exception` and either pass or return a generic error without logging (e.g. `db_registry.py`, `amaiz_service.py`, `learning_agent.py`).
- **Configuration inside request path**: Settings loaded repeatedly in hot paths instead of at startup or via dependency injection.
- **Long parameter lists**: Some functions take many optional parameters; could use request/context objects.

---

## Performance

- **No connection pooling configuration**: Postgres/Couchbase connection lifecycle is per-request or ad hoc; pooling limits not centralized.
- **Schema cache TTL fixed**: Cache invalidation is time-based only; no event-based invalidation on schema change.
- **Large payloads**: Chat and analyze-query can build large prompts; no streaming or chunking for very large contexts.
- **Synchronous file I/O**: Report upload and parsing use sync read; could use async for large files.

---

## Security

- **Credentials in config defaults**: `couchbase_connection_string` and Postgres defaults in config/env; ensure .env is never committed and production overrides all defaults.
- **API key in header only**: No rotation story or key scope; single key for all access.
- **CORS extra origins**: Hardcoded `https://tracewise-ui:8443` in app.py; should be explicitly set per environment.
- **File upload types**: Allowed extensions are fixed in code (`.html`, `.htm`, `.txt`, etc.); consider configurable allow-list and virus scanning for production.

---

## Dependencies

- **requirements-prod.txt vs requirements.txt**: If both exist, version ranges may differ; can cause "works in dev, fails in prod."
- **Couchbase optional**: `acouchbase` commented out in prod; Couchbase connector will fail at runtime if used without installing it.
- **No pinned transitive deps**: Only direct dependencies pinned; transitive versions can change over time.
- **HTTPX_REQUEST_TIMEOUT in Dockerfile**: Hardcoded 1024 in Dockerfile; should align with config/env.

---

## Error handling

- **Generic 500 responses**: Unhandled exceptions return a single "Internal server error" message; no correlation ID or structured error code for clients.
- **No retry policy**: External calls (AMAIZ, DB) have limited or ad hoc retry; no standard backoff/retry configuration.
- **WebSocket errors**: Exceptions in WebSocket handler are caught broadly; client may not get a clear close reason.

---

## Naming and consistency

- **Inconsistent naming**: Mix of `connection_id` / `conn_id`, `dsn` / `DSN`; some schemas use camelCase in JSON, others snake_case.
- **Version**: App version "7.0.0" appears in app.py and routes; ensure single source of truth (e.g. one constant or config).

---

## Directory structure

- **Flat backend layout**: Many modules under `backend/` at same level; `api/`, `core/`, `agents/`, `intelligence/` could have clearer boundaries and fewer cross-imports.
- **Tests outside backend**: Tests live under `tests/`; running them requires project root on `PYTHONPATH` or running from v7 root.

---

## Redundant / unused

- **Commented proxy in Dockerfile**: `http_proxy` / `https_proxy` commented; remove or document for corporate environments.
- **Optional MCP/Keycloak**: Large surface area for optional features; ensure unused code paths are not loaded at startup if disabled.

---

## Inconsistent patterns

- **Response models**: Some endpoints return Pydantic models, others return raw dicts; inconsistent OpenAPI documentation.
- **Pagination**: No standard pattern for list endpoints (e.g. `/api/issues`, `/api/insights`); limits (e.g. 500) are hardcoded in routes.
