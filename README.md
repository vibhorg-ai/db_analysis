# DB Analyzer AI v7

Enterprise database intelligence platform with 12 AI agents, real-time monitoring, knowledge graph, time-travel analytics, and a modern React UI.

## Architecture

- **Backend:** FastAPI (Python 3.12+), 12 specialized AI agents orchestrated by a pipeline engine
- **Frontend:** React 19 + TypeScript + Tailwind CSS (Vite)
- **LLM:** AMAIZ SDK integration with circuit breaker and retry logic
- **Databases:** PostgreSQL (asyncpg), Couchbase (acouchbase), MCP adapter fallback
- **Auth:** Keycloak SSO (JWT), API key, or dev mode (auto-selected)

## Supported Databases

| Database   | Connector        | Features                                     |
|------------|------------------|----------------------------------------------|
| PostgreSQL | asyncpg (native) | Schema introspection, query plans, health metrics |
| Couchbase  | acouchbase SDK   | Bucket/scope/collection schema, N1QL queries |

Both connectors support connection pooling, health checks, and MCP bridge fallback.

## Quick Start

### 1. Clone and configure

```bash
git clone git@github.com:vibhorg-ai/db_analysis.git
cd db_analysis
cp .env.example .env          # Fill in AMAIZ credentials and DB settings
cp db_connections.example.yaml db_connections.yaml  # Fill in DB credentials
```

### 2. Backend

```bash
pip install -r requirements.txt
python run_api.py              # Starts on http://127.0.0.1:8004
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev                    # Starts on http://localhost:3000, proxies API to :8004
```

### 4. Production build

```bash
cd frontend
npm run build                  # Output in dist/, served by backend
```

## Environment Variables

Copy `.env.example` to `.env` and fill in the values. **Never commit `.env`.**

| Variable | Required | Description |
|----------|----------|-------------|
| `AMAIZ_TENANT_ID` | Yes | AMAIZ platform tenant ID |
| `AMAIZ_BASE_URL` | Yes | AMAIZ portal URL |
| `AMAIZ_API_KEY` | Yes | AMAIZ API key |
| `AMAIZ_GENAIAPP_RUNTIME_ID` | Yes | AMAIZ GenAI app runtime ID |
| `POSTGRES_DSN` | Yes* | PostgreSQL connection string |
| `COUCHBASE_CONNECTION_STRING` | No | Couchbase connection string |
| `COUCHBASE_BUCKET` | No | Couchbase bucket name |
| `COUCHBASE_USERNAME` | No | Couchbase username |
| `COUCHBASE_PASSWORD` | No | Couchbase password |
| `KEYCLOAK_SERVER_URL` | No | Keycloak URL (leave empty for dev mode) |
| `KEYCLOAK_REALM` | No | Keycloak realm |
| `KEYCLOAK_CLIENT_ID` | No | Keycloak client ID |
| `KEYCLOAK_CLIENT_SECRET` | No | Keycloak client secret |
| `API_KEY` | No | Static API key (alternative to Keycloak) |
| `LOG_LEVEL` | No | Logging level (default: INFO) |

*At least one database connection is required.

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
| GET | /api/index-recommendations | analyze | Get index recommendations |
| GET | /api/db-health | view_health | Database health metrics |
| GET | /api/mcp-status | - | MCP configuration status |
| POST | /api/chat | chat | Chat with AI (supports HTML report upload) |
| POST | /api/sandbox | sandbox_access | Execute sandboxed query |
| GET | /health/live | - | Liveness probe |
| GET | /health/ready | - | Readiness probe |
| GET | /metrics | - | Prometheus metrics |
| WS | /ws | - | WebSocket real-time events |

## Authentication

Three modes (auto-selected based on config):

1. **Keycloak SSO:** Set `KEYCLOAK_SERVER_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID` in `.env`. JWT tokens validated, roles extracted.
2. **API Key:** Set `API_KEY` in `.env`. Pass via `X-API-Key` header or `Authorization: Bearer <key>`.
3. **Dev Mode:** Neither configured -- all endpoints open with admin role.

### Roles

| Role | Permissions |
|------|------------|
| admin | All operations |
| analyst | Query, sandbox, schema, health, chat, analyze, reports |
| viewer | Schema, health, issues, chat (read-only) |

## 12 AI Agents

1. **Schema Intelligence** -- Schema structure analysis
2. **Query Analysis** -- SQL query pattern detection
3. **Optimizer** -- Performance optimization suggestions
4. **Index Advisor** -- Index recommendations
5. **Workload Intelligence** -- Workload pattern analysis
6. **Monitoring** -- Health metric analysis
7. **Blast Radius** -- Change impact prediction
8. **Report Analysis** -- External report parsing
9. **Graph Reasoning** -- Knowledge graph pattern detection
10. **Time Travel** -- Historical trend analysis
11. **Self-Critic** -- Output quality review
12. **Learning** -- Insight extraction and persistence

## Project Structure

```
backend/
  api/           # FastAPI app, routes, schemas, WebSocket
  agents/        # 12 agents + orchestrator
  connectors/    # PostgreSQL, Couchbase, base protocol
  core/          # Config, auth, AMAIZ, LLM router, circuit breaker, etc.
  graph/         # Knowledge graph, entity graph, dependency engine
  intelligence/  # Autonomous advisor, simulation engine
  mcp/           # MCP bridge
  scheduler/     # Autonomous monitoring and advisor scheduler
  time_travel/   # Schema/query/performance/issue history
frontend/
  src/
    api/         # API client, WebSocket client
    components/  # Layout, ChatWidget
    context/     # App context provider
    pages/       # Dashboard pages
prompts/         # Agent prompt markdown files
  amaiz/         # AMAIZ platform prompt configs and schemas
docs/            # Testing guides and improvement docs
tests/           # pytest + Playwright test suite
```

## Testing

**Unit / API tests (pytest):**
```bash
python -m pytest tests/ -v
```

**E2E browser tests (Playwright):**
Start backend and frontend, then from `tests/e2e` run `npm install`, `npx playwright install chromium`, and `npm test`. See `tests/e2e/README.md` for details.
