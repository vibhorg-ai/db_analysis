#!/usr/bin/env bash
set -euo pipefail

# Generate self-signed TLS certificates for Traefik (dev/staging).
# Run from the docker/traefik/ directory:  ./generate-certs.sh
# Requires: openssl

CERTS_DIR="$(cd "$(dirname "$0")/certs" && pwd)"
CN_HOST="${1:-db-analyzer.local}"

echo "==> Generating certificates in ${CERTS_DIR}"
echo "    Hostname (CN / SAN): ${CN_HOST}"

# --- CA ---
openssl req -x509 -newkey rsa:4096 \
  -keyout "${CERTS_DIR}/ca.key" \
  -out "${CERTS_DIR}/ca.pem" \
  -days 3650 -nodes \
  -subj "/CN=DB Analyzer CA"

echo "==> CA created (ca.key, ca.pem)"

# --- Server OpenSSL config with SANs ---
cat > "${CERTS_DIR}/server.cnf" <<EOF
[req]
default_bits       = 2048
prompt             = no
default_md         = sha256
distinguished_name = dn
req_extensions     = v3_req

[dn]
CN = ${CN_HOST}

[v3_req]
subjectAltName = @alt_names

[alt_names]
DNS.1 = ${CN_HOST}
DNS.2 = localhost
IP.1  = 127.0.0.1
EOF

echo "==> server.cnf written"

# --- Server key + CSR ---
openssl req -new -newkey rsa:2048 \
  -keyout "${CERTS_DIR}/key.pem" \
  -out "${CERTS_DIR}/server.csr" \
  -nodes \
  -config "${CERTS_DIR}/server.cnf"

echo "==> Server key (key.pem) and CSR (server.csr) created"

# --- Sign with CA ---
openssl x509 -req \
  -in "${CERTS_DIR}/server.csr" \
  -CA "${CERTS_DIR}/ca.pem" \
  -CAkey "${CERTS_DIR}/ca.key" \
  -CAcreateserial \
  -out "${CERTS_DIR}/cert.pem" \
  -days 365 -sha256 \
  -extensions v3_req \
  -extfile "${CERTS_DIR}/server.cnf"

echo "==> Server certificate (cert.pem) signed by CA"
echo ""
echo "Files generated in ${CERTS_DIR}:"
ls -la "${CERTS_DIR}"/*.pem "${CERTS_DIR}"/*.key "${CERTS_DIR}"/*.csr "${CERTS_DIR}"/*.srl "${CERTS_DIR}"/*.cnf 2>/dev/null || true
echo ""
echo "Done. Traefik uses cert.pem and key.pem."
