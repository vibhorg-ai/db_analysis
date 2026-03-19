# API Routes Package

The main API router is composed here. Structure:

- **`__init__.py`** — Exports `router` (imported from `_routes_monolith`). Use `from backend.api.routes import router`.
- **`health.py`** — Sub-router for `/health` and `/health/amaiz`. Included by the monolith.
- **`shared.py`** — Shared state and helpers for future sub-routers (connection state, sanitize_error, resolve_connection, etc.).
- **`_routes_monolith.py`** (in parent `api/`) — Contains the rest of the route handlers. Can be split further into `connections.py`, `analysis.py`, `chat.py`, etc., by moving handlers and including sub-routers.

To split more routes: create a new file (e.g. `connections.py`), define an `APIRouter()`, add the route handlers, then in `_routes_monolith.py` do `router.include_router(connections.router)` and remove the moved handlers.
