# E2E tests (Playwright)

Browser tests for DB Analyzer v5. Run against a live frontend + API.

## Prerequisites

1. **Backend** (from `v5`): `python run_api.py` — default port 8002 (or set in `.env`).
2. **Frontend** (from `v5/frontend`): `npm run dev` — default port 3000, proxies `/api`, `/health`, `/ws` to backend.

Ensure `v5/frontend/vite.config.ts` proxy target matches your backend port (e.g. 8002 or 8003).

## Install and run

```bash
cd v5/tests/e2e
npm install
npx playwright install chromium
npm test
```

## Options

- **Different base URL**: `BASE_URL=http://localhost:3000 npm test`
- **Headed browser**: `npm run test:headed`
- **UI mode**: `npm run test:ui`

## Tests

- Home page loads and shows app title
- Navigation: Dashboard, Query, Health, Sandbox, Chat, Simulation
- Health page content
- Sandbox: query input and Run button
- Chat: message input and Send button
- Simulation: type selector and Run Simulation button
- API health: `GET /health/live` returns `{"status":"ok"}`
