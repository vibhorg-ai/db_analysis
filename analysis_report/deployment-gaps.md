# Static Analysis — Deployment Gaps (v7)

Issues that can prevent reliable local or containerized deployment.  
A minimal **deployment_clean/** folder is provided separately for backend-only production deployment.

---

## 1. Environment and config

- **.env not committed**: Application expects `.env`; new clones must copy `.env.example` to `.env` and fill values. Document in README as a required step.
- **Frontend proxy**: Dev server proxy target (e.g. in vite.config.ts) may default to `http://localhost:8004` or `https://db-analyzer:9443`. For Docker or remote backend, user must set the correct target. Not always obvious for first-time run.
- **Python path**: Running tests or scripts from `v7/tests/` or other subdirs requires `PYTHONPATH=v7` or running from `v7` so that `backend` is importable. README should state “run from v7 root” or document `PYTHONPATH`.

---

## 2. Local run

- **Backend**: `python run_api.py` from v7 root works if dependencies are installed (`pip install -r requirements-prod.txt`) and `.env` exists. The **deployment_clean/** folder includes `run_local.ps1` and `run_local.sh` for a minimal one-command local run.
- **Frontend**: Requires Node/npm; `npm install` and `npm run dev` from `v7/frontend`. No single script that starts both backend and frontend for local dev.
- **Data directories**: Backend expects `data/`, `memory/`, `reports/` (or configured paths). They are created in Dockerfile and in deployment_clean; when running locally from v7 root, create them if missing or document in README.

---

## 3. Docker

- **Build context**: Dockerfile assumes build from v7 root (or deployment_clean root); `COPY backend/`, `COPY prompts/`, `COPY run_api.py` are correct. `docker compose -f docker/docker-compose.yml` must be run from v7 root so that `context: ..` and `env_file: ../.env` resolve.
- **Port mismatch**: Compose exposes `8004:8004` and backend uses `APP_PORT`; if user sets `APP_PORT` to something else in `.env`, compose still maps 8004 on host unless compose is updated to use `${APP_PORT}`. Document that host port in compose should match `APP_PORT` or use variable.
- **Traefik**: Compose includes Traefik with fixed hostname `db-analyzer` in labels; local dev behind Traefik requires that hostname or DNS/hosts entry. Not an issue for “backend only” run.
- **No production compose in v7 root**: Single compose file is dev/Traefik-oriented; minimal “backend only” deployment is in **deployment_clean/** (Dockerfile + run scripts, no compose).

---

## 4. Dependencies

- **Couchbase**: Production requirements comment out `acouchbase`. If Couchbase is used, image build must add it or a second stage; otherwise Couchbase connector will fail at runtime.
- **Node for frontend**: Building the frontend for production (e.g. `npm run build`) requires Node; not in the backend Dockerfile. Backend image does not serve the frontend; separate build or multi-stage needed for a single image serving both.

---

## 5. Health and readiness

- **/health/ready**: Does not currently check DB or AMAIZ connectivity; readiness could still be “ok” when downstream is failing. Consider optional readiness checks that probe DB/AMAIZ when configured.
- **Startup order**: If using compose with DB or AMAIZ, no `depends_on` or wait logic for backend to wait for those services.

---

## 6. Secrets and security

- **Secrets in .env**: All secrets in `.env`; production should use a secret manager or orchestration secrets and pass via env, not a committed file. Document “do not commit .env.”
- **Default CORS**: `CORS_ALLOWED_ORIGINS=*` is permissive; production should set explicit origins.

---

## 7. Logging and observability

- **Log level**: Configurable via `LOG_LEVEL`; default INFO. No structured (JSON) logging option documented for production.
- **Metrics**: Prometheus endpoint present; no default scrape config or dashboard referenced in repo.

---

## 8. deployment_clean (provided)

The **deployment_clean/** folder in v7 contains:

- Backend code, prompts, run_api.py, requirements, production Dockerfile, .dockerignore, .env.template, and run_local.ps1 / run_local.sh.
- No frontend, tests, docs, IDE configs, or dev artifacts.
- Intended for minimal, production-ready backend image and local run.

---

## Summary

| Gap | Severity | Mitigation |
|-----|----------|------------|
| .env and first-run setup | High | Document in README; use .env.template and run_local script in deployment_clean. |
| PYTHONPATH / run from root | Medium | Document “run from v7”; run script in deployment_clean sets path. |
| Frontend proxy / port | Medium | Document proxy target and default ports in README. |
| Compose port vs APP_PORT | Low | Document or use variable in compose. |
| Couchbase in prod image | Medium | Document; add optional stage or doc to uncomment dep. |
| deployment_clean | Done | Provided with Dockerfile, .env.template, run_local scripts. |
| Readiness not probing deps | Low | Optional: add DB/AMAIZ checks to `/health/ready`. |
