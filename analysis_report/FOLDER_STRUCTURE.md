# v7 Folder-by-Folder Explanation

Purpose, contents, and whether each folder belongs in production or development-only.

---

## backend/

**Purpose**: Core application code for the DB Analyzer AI API.

**Contains**:
- `api/` — FastAPI app, routes, schemas, WebSocket handler.
- `core/` — Config, auth, metrics, connection manager, db_registry, chat_session, report_parser, health_monitor, circuit_breaker, agent_router, amaiz_service, llm_router, prompt_trim, schema_cache, instance_id.
- `connectors/` — Postgres and Couchbase connectors, MCP adapter, base protocol.
- `agents/` — Agent orchestrator and individual agents (schema, query, workload, optimizer, blast_radius, etc.).
- `intelligence/` — Simulation engine, autonomous advisor, workload analyzer, insight generator.
- `graph/` — Entity graph, dependency engine, query plan graph.
- `time_travel/` — Issue, query, schema, performance history stores.
- `scheduler/` — Monitoring and advisor jobs.
- `mcp/` — MCP bridge.

**Production**: Yes. Required to run the API. Included in **deployment_clean/**.

---

## frontend/

**Purpose**: React (Vite + TypeScript) UI for dashboards, chat, connections, health, sandbox, etc.

**Contains**: Source under `src/`, Vite config, package.json, static assets.

**Production**: No for backend-only. Development/optional. Excluded from **deployment_clean/**.

---

## prompts/

**Purpose**: Prompt and schema assets used at runtime; AMAIZ setup docs.

**Contains**: Prompt content; `amaiz/` subfolder has setup guides and schemas (excluded from Docker image via .dockerignore in v7 and deployment_clean).

**Production**: Partially. Runtime prompts are needed; `prompts/amaiz/` is documentation/setup-only. **deployment_clean** copies `prompts/` but .dockerignore excludes `prompts/amaiz/` for a smaller image.

---

## tests/

**Purpose**: Pytest API/connector/report tests, system test runner, E2E Playwright tests.

**Contains**: `test_*.py`, `conftest.py`, `api_test_battery.py`, `system_test_runner.py`, `run_all_tests.py`, `e2e/` (Playwright).

**Production**: No. Development and CI only. Excluded from **deployment_clean/**.

---

## docker/

**Purpose**: Docker Compose stack (Traefik + backend) and Traefik config/certs for local HTTPS.

**Contains**: `docker-compose.yml`, `traefik/`, `check-api-endpoints.ps1`, `README.md`.

**Production**: Optional. Used for local or dev deployment with Traefik. Not part of **deployment_clean/** (which is a single-service backend image).

---

## docs/

**Purpose**: Testing checklists, system testing notes, improvement proposals.

**Contains**: `testing/`, `improvements/`.

**Production**: No. Documentation only. Excluded from **deployment_clean/**.

---

## tasks/

**Purpose**: Development plans, todo, lessons, audit notes.

**Contains**: `todo.md`, `lessons.md`, `audit_backend_bugs.md`, `system_test_report.md`.

**Production**: No. Development only. Excluded from **deployment_clean/**.

---

## analysis_report/

**Purpose**: Static analysis deliverables (no runtime use).

**Contains**: `issues.md`, `recommendations.md`, `missing-tests.md`, `deployment-gaps.md`, `hardcoded_values.md`, `FOLDER_STRUCTURE.md`.

**Production**: No. For engineers reviewing the codebase. Not needed in container or runtime.

---

## deployment_clean/

**Purpose**: Minimal, production-ready backend-only deployment.

**Contains**:
- `backend/`, `prompts/`, `run_api.py`, `requirements.txt`
- `Dockerfile`, `.dockerignore`, `.env.template`
- `run_local.ps1`, `run_local.sh`, `README.md`

**Production**: Yes. Use this folder to build the backend image and run locally without frontend or dev artifacts.

---

## memory/, data/, reports/

**Purpose**: Runtime directories for learning agent memory, custom connections/data, and report output.

**Contains**: Created at runtime or by Dockerfile; may be empty in repo.

**Production**: Yes as mount points or created dirs. Dockerfile creates `data`, `memory`, `reports`; mount or bind as needed.

---

## Root files (v7)

- `run_api.py` — ASGI entrypoint (Uvicorn). **Production**: Yes.
- `requirements-prod.txt` — Production Python deps. **Production**: Yes (copied as `requirements.txt` in deployment_clean).
- `Dockerfile` — Full v7 build (same layout as deployment_clean). **Production**: Yes.
- `.dockerignore`, `.env.example`, `.env` — Config and env template. **Production**: .env not committed; .env.example/.env.template for setup.
- `README.md` — Project readme. **Production**: Documentation only.

---

## Summary

| Folder / area        | In production backend? | In deployment_clean? |
|----------------------|------------------------|----------------------|
| backend/             | Yes                    | Yes                  |
| frontend/            | No                     | No                   |
| prompts/             | Yes (subset)           | Yes (amaiz excluded in image) |
| tests/               | No                     | No                   |
| docker/              | Optional (compose)     | No                   |
| docs/, tasks/        | No                     | No                   |
| analysis_report/     | No                     | No                   |
| deployment_clean/    | N/A (is the deploy)   | Yes (self-contained) |
| memory/, data/, reports/ | As dirs/mounts     | Created in image     |
