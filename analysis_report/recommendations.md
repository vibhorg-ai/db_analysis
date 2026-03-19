# Static Analysis — Recommendations (v7)

Improvements suggested, with brief examples where helpful. **No changes were made** to functionality.

---

## 1. Error handling and logging

- **Log before re-raise or return**: For every `except Exception`, log with `logger.exception(...)` or `logger.warning(...)` and then re-raise or return a structured error.
- **Structured errors**: Return a consistent shape, e.g. `{ "error": { "code": "CONNECTION_FAILED", "message": "...", "request_id": "..." } }` and use a single exception handler that maps exceptions to codes.
- **Request/correlation ID**: Already have `X-Request-ID`; ensure it is included in all log lines and optional error response body for support.

Example for routes:

```python
except Exception as e:
    logger.exception("Chat failed request_id=%s", request.state.request_id)
    raise HTTPException(status_code=500, detail=_sanitize_error(str(e)))
```

---

## 2. Configuration and DI

- **Inject settings in FastAPI**: Use `Depends(get_settings)` for route parameters so settings are resolved once per request and testable.
- **Constants for engines**: Define `class Engine(str, Enum): POSTGRES = "postgres"; COUCHBASE = "couchbase"` and use everywhere instead of string literals.

---

## 3. Split routes and domain

- **Sub-routers**: Split `routes.py` into e.g. `routes/connections.py`, `routes/chat.py`, `routes/analysis.py`, `routes/health.py` and include them with prefixes.
- **Service layer**: Introduce e.g. `ConnectionService`, `ChatService`, `AnalysisService` that hold business logic; routes only validate input and call services. Improves testability and reuse.

---

## 4. Sessions and state

- **Session persistence**: Provide an optional session store backend (e.g. Redis or DB) so chat sessions survive restarts; keep in-memory as default for dev.
- **Connection manager**: Consider moving connection state behind a dedicated service/interface so it can be mocked or replaced.

---

## 5. Dependencies and build

- **Unify requirement files**: Use a single base (e.g. `requirements.in` with `pip-tools`) or align version specifiers between `requirements.txt` and `requirements-prod.txt`.
- **Pin transitive deps in prod**: Generate `requirements-prod.txt` with `pip freeze` or use `pip-tools compile` for reproducible builds.
- **Couchbase**: Either add `acouchbase` to prod requirements when Couchbase is used, or make the Couchbase connector a lazy optional import with a clear error message when not installed.
- **Dockerfile ENV**: Align `HTTPX_REQUEST_TIMEOUT` in Dockerfile with config (e.g. use ARG or document that .env overrides it at runtime).

---

## 6. Security

- **API key scope**: Support multiple keys or scopes (e.g. read-only vs full) and document rotation.
- **File upload**: Make allowed extensions and max size fully configurable; consider virus scanning for production.
- **Secrets**: Ensure no default secrets in config; use empty defaults and require explicit env in production (with startup check).
- **CORS**: Move hardcoded `tracewise-ui:8443` into config or env so production can override.

---

## 7. Performance and resilience

- **Connection pooling**: Centralize pool size and timeout configuration for Postgres and Couchbase.
- **Streaming**: For very large chat/analyze payloads, consider streaming responses or chunking context.
- **Retry/backoff**: Standardize retry policy for AMAIZ and DB calls (e.g. tenacity or backoff config in settings).

---

## 8. Hardcoded values

- **Ports and hosts**: Document default ports (8004, 3000, 9080, 9443) in README; prefer env for overrides.
- **Rate limit**: Move 100/60 (requests/window) into config so production can tune.
- **Limits**: Pagination (500), file size (20 MB), query length (50K), session/message limits — consider making these configurable.

See `hardcoded_values.md` for the full list.
