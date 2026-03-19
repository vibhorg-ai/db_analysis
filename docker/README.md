# Docker Setup — DB Analyzer AI v7

All Docker-related files live in this folder.

## Layout

```
v7/
  Dockerfile              # Backend image (context = v7/)
docker/
  docker-compose.yml      # Compose stack (Traefik + backend)
  traefik/
    traefik.yml            # Traefik static config
    generate-certs.sh      # TLS cert generator (bash)
    generate-certs.ps1     # TLS cert generator (PowerShell)
    certs/                 # Generated TLS certificates
```

## Usage

From **v7/** root:

```bash
# Build the backend image (Dockerfile is in v7/, so run from v7/)
docker build -t db-analyzer-backend:v7 .

# Start the stack (Traefik + backend; compose builds backend if needed)
docker compose -f docker/docker-compose.yml up -d

# Stop
docker compose -f docker/docker-compose.yml down

# Validate compose config
docker compose -f docker/docker-compose.yml config
```

## TLS Certificates

Self-signed dev certs live in `docker/traefik/certs/` and are mounted
into the Traefik container. To regenerate:

```bash
cd docker/traefik
./generate-certs.sh          # bash
.\generate-certs.ps1         # PowerShell
```

See `docker/traefik/certs/README.md` for details.

## Ports

| Service  | Port  | Protocol |
|----------|-------|----------|
| Backend  | 8004  | HTTP     |
| Traefik  | 9080  | HTTP     |
| Traefik  | 9443  | HTTPS    |
