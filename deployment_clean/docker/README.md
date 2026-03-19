# Docker — DB Analyzer AI v7 (`deployment_clean`)

Docker-related assets for the **v7 deployment_clean** tree. The **`Dockerfile`** and **`docker-compose.yml`** live in the **parent directory** (`deployment_clean/`); run all `docker` / `docker compose` commands from there.

## Layout

```
deployment_clean/          # repository / package root
  Dockerfile
  docker-compose.yml
  .env                     # local only; not in Git
  db_connections.yaml      # local only; not in Git
docker/
  README.md                # this file
  check-api-endpoints.ps1
  traefik/
    traefik.yml
    generate-certs.sh
    generate-certs.ps1
    certs/                 # generated TLS files (gitignored)
```

## Compose stack (Traefik + backend)

From **`deployment_clean/`**:

```bash
docker build -t db-analyzer:latest .
docker compose up -d
docker compose down
docker compose config   # validate compose file
```

See the root **`README.md`** for `.env`, `db_connections.yaml`, TLS generation, ports, and host (`db-analyzer`) notes.

## TLS certificates

Self-signed dev certs for Traefik live in `docker/traefik/certs/` and are mounted read-only into the Traefik container.

Regenerate from `docker/traefik/`:

```bash
./generate-certs.sh       # Unix
.\generate-certs.ps1      # PowerShell
```

## Ports

| Service  | Host port | Protocol |
|----------|-----------|----------|
| Backend  | 8004      | HTTP     |
| Traefik  | 9080      | HTTP     |
| Traefik  | 9443      | HTTPS    |
