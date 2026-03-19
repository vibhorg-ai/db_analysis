# TLS Certificates for Traefik

## Quick start

Run the generation script from the `docker/traefik/` directory:

```bash
# Bash (Git Bash / WSL / Linux / macOS)
./generate-certs.sh

# PowerShell (Windows — requires openssl on PATH)
.\generate-certs.ps1
```

## Generated files

| File         | Purpose                                      |
|--------------|----------------------------------------------|
| `ca.key`     | CA private key (RSA 4096)                    |
| `ca.pem`     | CA self-signed certificate                   |
| `ca.srl`     | CA serial number file                        |
| `server.cnf` | OpenSSL config with SANs                     |
| `server.csr` | Server certificate signing request           |
| `key.pem`    | Server private key (RSA 2048)                |
| `cert.pem`   | Server certificate signed by CA              |

## What Traefik uses

Only **`cert.pem`** and **`key.pem`** are referenced in `traefik.yml`.
The other files are kept for re-issuing or verification.

## Security

These are **self-signed development certificates**.
For production, replace `cert.pem` and `key.pem` with certificates
issued by your organization's CA or a public CA.

Do not commit private keys to the repository.
