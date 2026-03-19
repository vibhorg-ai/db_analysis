# DB Analyzer AI v7 — Backend deployment

Minimal, production-oriented backend API (FastAPI). This package is **backend-only**: no frontend, tests, or dev-only artifacts in the default image.

---

## Prerequisites

| Context | Requirement |
|--------|-------------|
| **Local Python** | Python **3.12+**, `pip` |
| **Docker** | Docker Engine + Docker Compose v2 (optional; for container deployment) |
| **Corporate packages** | AMAIZ wheels are installed from **Amdocs Nexus** during `docker build` and may be required for a full local `pip install` if you use the same `requirements.txt` / index URLs |

---

## First-time setup

Do this once after cloning.

1. **Environment file**  
   Copy the template and edit:

   ```bash
   cp .env.template .env
   ```

   - **Minimal run**: set `APP_HOST` / `APP_PORT` if you need non-defaults (defaults: `0.0.0.0`, `8004`).  
   - **AMAIZ features**: fill `AMAIZ_*` variables (see comments in `.env.template`).  
   - **Databases**: set `POSTGRES_DSN`, Couchbase vars, and/or MCP vars as needed.  
   - **Optional auth**: Keycloak (`KEYCLOAK_*`), `API_KEY`, CORS (`CORS_ALLOWED_ORIGINS`, `CORS_EXTRA_ORIGINS`).

2. **DB connections file**  
   The app loads connection definitions from `db_connections.yaml` at the repo root.

   ```bash
   cp db_connections.example.yaml db_connections.yaml
   ```

   Edit `db_connections.yaml` with your environments (no real secrets in Git — file is listed in `.gitignore`).

3. **Install dependencies (local only)**

   ```bash
   pip install -r requirements.txt
   ```

   If `pip` cannot reach private indexes, use the same `--extra-index-url` / `--trusted-host` values your team uses for AMAIZ (the `Dockerfile` shows the Nexus URLs used for image builds).

---

## Run locally (without Docker)

From this directory (`deployment_clean`):

- **Windows** (PowerShell):

  ```powershell
  .\run_local.ps1
  ```

- **Linux / macOS**:

  ```bash
  chmod +x run_local.sh
  ./run_local.sh
  ```

Scripts require a `.env` file in this directory (see above).

| URL | Purpose |
|-----|---------|
| `http://localhost:8004` | API (or `http://<APP_HOST>:<APP_PORT>`) |
| `http://localhost:8004/docs` | OpenAPI (Swagger UI) |

---

## Run with Docker Compose (Traefik + HTTPS)

Stack: **Traefik** (TLS on host) + **backend** image. Compose file and `Dockerfile` live at the **root of this folder**.

### 1. TLS certificates

Traefik expects `cert.pem` and `key.pem` under `docker/traefik/certs/`. Generate self-signed dev certs:

- **PowerShell** (from repo root):

  ```powershell
  cd docker/traefik
  .\generate-certs.ps1
  ```

- **Bash**:

  ```bash
  cd docker/traefik
  chmod +x generate-certs.sh
  ./generate-certs.sh
  ```

Generated `*.pem` / `*.key` files are **ignored by Git** (see `docker/traefik/certs/.gitignore`). Trust the CA or accept the browser warning for dev.

### 2. `.env` and `db_connections.yaml`

- Ensure `.env` exists (from `.env.template`). Compose uses `env_file: .env` for the backend service.  
- Ensure `db_connections.yaml` exists (copy from `db_connections.example.yaml`). Compose mounts it read-only into the container.

### 3. Build and start

From **`deployment_clean`** (this directory):

```bash
docker build -t db-analyzer:latest .
docker compose up -d
```

The `Dockerfile` installs Python deps from `requirements-nohash.txt` using the corporate Nexus index baked into the image recipe; you need network access to that host for the build to succeed.

Default published ports (see `docker-compose.yml`):

| Port | Service |
|------|---------|
| **8004** | Backend HTTP (direct) |
| **9080** | Traefik HTTP |
| **9443** | Traefik HTTPS |

The Traefik router is configured with **`Host(\`db-analyzer\`)`** for HTTPS. For local access you typically add a hosts entry, for example:

```text
127.0.0.1   db-analyzer
```

Then open: `https://db-analyzer:9443` (path `/docs` for Swagger).

Stop the stack:

```bash
docker compose down
```

### Single-container run (no Traefik)

```bash
docker build -t db-analyzer-backend:v7 .

docker run -p 8004:8004 --env-file .env \
  -v /path/to/your/db_connections.yaml:/app/db_connections.yaml:ro \
  db-analyzer-backend:v7
```

The image ships a default `db_connections.yaml` derived from `db_connections.example.yaml`; override by mounting your real file as above.

---

## Volumes and persistence

When using Compose, these host directories are mounted into the container:

- `data/` — application data  
- `memory/` — persisted memory / insights-style state  
- `reports/` — reports output  

They are created as needed and are **ignored by Git** in this repo so local state is not committed.

---

## Security (Git and images)

- **Do not commit** `.env` or real `db_connections.yaml`. Use `.env.template` and `db_connections.example.yaml` only in the repository.  
- **`.env` is not baked into the image**; pass configuration with `--env-file` or orchestration secrets.  
- TLS private keys under `docker/traefik/certs/` must not be committed (patterns in `certs/.gitignore`).

---

## Repository layout

| Path | Role |
|------|------|
| `backend/` | API, core, connectors, agents, intelligence, schedulers |
| `prompts/` | Runtime prompt files |
| `run_api.py` | ASGI entrypoint (`PYTHONPATH` = repo root) |
| `requirements.txt` | Locked-ish deps for local/prod installs |
| `requirements-nohash.txt` | Used by `Dockerfile` for image builds |
| `db_connections.example.yaml` | Template for `db_connections.yaml` |
| `Dockerfile`, `.dockerignore` | Container build |
| `.env.template` | Environment variable template |
| `run_local.ps1`, `run_local.sh` | Local dev runners |
| `docker/` | Compose-oriented Traefik config, cert scripts, `docker/README.md` |

---

## Troubleshooting

| Issue | What to check |
|-------|----------------|
| **Port already in use** | Change `APP_PORT` in `.env` or adjust published ports in `docker-compose.yml`. |
| **Compose fails: missing `db_connections.yaml`** | `cp db_connections.example.yaml db_connections.yaml` before `docker compose up`. |
| **pip / build fails on AMAIZ packages** | Network/VPN to Nexus; for local `pip`, mirror the index URLs in `Dockerfile`; image builds use those URLs by default. |
| **HTTPS returns 404 / wrong host** | Router uses host `db-analyzer`; add a hosts file entry or align Traefik labels with your hostname. |
| **`run_local` exits immediately** | Ensure `.env` exists next to `run_local.ps1` / `run_local.sh`. |

---

## Default port

**8004**, overridable with `APP_PORT` in `.env`.
