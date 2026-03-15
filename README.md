# DB Analyzer AI v5

Enterprise database intelligence platform with 12 AI agents, real-time monitoring, knowledge graph, time-travel analytics, and a modern React UI.

## Architecture

- **Backend:** FastAPI (Python 3.12+), 12 specialized AI agents orchestrated by a pipeline engine
- **Frontend:** React 19 + TypeScript + Tailwind CSS (Vite)
- **LLM:** AMAIZ SDK integration with circuit breaker and retry logic
- **Databases:** PostgreSQL (asyncpg), Couchbase (acouchbase), MCP adapter fallback
- **Auth:** Keycloak SSO (JWT), API key, or dev mode (auto-selected)

## Quick Start

### Backend

```bash
cd v5
cp .env.example .env    # Fill in AMAIZ credentials and DB settings
pip install -r requirements.txt
python run_api.py       # Starts on http://127.0.0.1:8002
```

### Frontend

```bash
cd v5/frontend
npm install
npm run dev             # Starts on http://localhost:3000, proxies API to :8002
```

### Production Build

```bash
cd v5/frontend
npm run build           # Output in dist/
```

## API Endpoints

| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| POST | /api/connect | db_manage | Connect to a database |
| POST | /api/disconnect/{id} | db_manage | Disconnect a database |
| GET | /api/connections | view_schema | List all connections |
| POST | /api/connections/add | db_manage | Add custom connection |
| DELETE | /api/connections/{id} | db_manage | Remove custom connection |
| GET | /api/schema | view_schema | Fetch schema metadata |
| POST | /api/analyze-query | analyze | Run analysis pipeline |
| POST | /api/analyze-report | analyze | Analyze uploaded report |
| GET | /api/index-recommendations | analyze | Get index recommendations |
| GET | /api/db-health | view_health | Database health metrics |
| GET | /api/mcp-status | - | MCP configuration status |
| POST | /api/chat | chat | Chat with the AI |
| POST | /api/sandbox | sandbox_access | Execute sandboxed query |
| GET | /health/live | - | Liveness probe |
| GET | /health/ready | - | Readiness probe |
| GET | /metrics | - | Prometheus metrics |
| WS | /ws | - | WebSocket real-time events |

## Authentication

Three modes (auto-selected based on config):

1. **Keycloak SSO:** Set `KEYCLOAK_SERVER_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID` in `.env`. JWT tokens validated, roles extracted.
2. **API Key:** Set `API_KEY` in `.env`. Pass via `X-API-Key` header or `Authorization: Bearer <key>`.
3. **Dev Mode:** Neither configured — all endpoints open with admin role.

### Roles

| Role | Permissions |
|------|------------|
| admin | All operations |
| analyst | Query, sandbox, schema, health, chat, analyze, reports |
| viewer | Schema, health, issues, chat (read-only) |

## 12 AI Agents

1. **Schema Intelligence** — Schema structure analysis
2. **Query Analysis** — SQL query pattern detection
3. **Optimizer** — Performance optimization suggestions
4. **Index Advisor** — Index recommendations
5. **Workload Intelligence** — Workload pattern analysis
6. **Monitoring** — Health metric analysis
7. **Blast Radius** — Change impact prediction
8. **Report Analysis** — External report parsing
9. **Graph Reasoning** — Knowledge graph pattern detection
10. **Time Travel** — Historical trend analysis
11. **Self-Critic** — Output quality review
12. **Learning** — Insight extraction and persistence

## Testing

```bash
cd v5
python -m pytest tests/ -v
```

33 tests covering connectors, agents, API endpoints, circuit breaker, knowledge graph, and dependency engine.

## Project Structure

```
v5/
  backend/
    api/         # FastAPI app, routes, schemas, WebSocket
    agents/      # 12 agents + orchestrator
    connectors/  # PostgreSQL, Couchbase, base protocol
    core/        # Config, auth, AMAIZ, LLM router, circuit breaker, etc.
    graph/       # Knowledge graph, entity graph, dependency engine
    mcp/         # MCP bridge
    scheduler/   # Autonomous monitoring scheduler
    time_travel/ # Schema/query/performance/issue history
  frontend/
    src/
      api/       # API client, WebSocket client
      components/# Layout
      pages/     # 8 dashboard pages
  prompts/       # Agent prompt markdown files
  memory/        # Learning agent persistent storage
  data/          # Custom connections YAML
  tests/         # pytest test suite
  tasks/         # Development plan and lessons
```

## Development Plan

See `tasks/todo.md` for the phased development checklist (Phases 1-9).
