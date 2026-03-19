# Generate self-signed TLS certificates for Traefik (dev/staging).
# Run from the docker\traefik\ directory:  .\generate-certs.ps1
# Requires: openssl on PATH (e.g. Git for Windows, Chocolatey, or manual install)

param(
    [string]$CnHost = "db-analyzer.local"
)

$ErrorActionPreference = "Stop"
$CertsDir = Join-Path $PSScriptRoot "certs"

Write-Host "==> Generating certificates in $CertsDir"
Write-Host "    Hostname (CN / SAN): $CnHost"

# --- CA ---
openssl req -x509 -newkey rsa:4096 `
  -keyout "$CertsDir\ca.key" `
  -out "$CertsDir\ca.pem" `
  -days 3650 -nodes `
  -subj "/CN=DB Analyzer CA"

Write-Host "==> CA created (ca.key, ca.pem)"

# --- Server OpenSSL config with SANs ---
$serverCnf = @"
[req]
default_bits       = 2048
prompt             = no
default_md         = sha256
distinguished_name = dn
req_extensions     = v3_req

[dn]
CN = $CnHost

[v3_req]
subjectAltName = @alt_names

[alt_names]
DNS.1 = $CnHost
DNS.2 = localhost
IP.1  = 127.0.0.1
"@

Set-Content -Path "$CertsDir\server.cnf" -Value $serverCnf -Encoding UTF8
Write-Host "==> server.cnf written"

# --- Server key + CSR ---
openssl req -new -newkey rsa:2048 `
  -keyout "$CertsDir\key.pem" `
  -out "$CertsDir\server.csr" `
  -nodes `
  -config "$CertsDir\server.cnf"

Write-Host "==> Server key (key.pem) and CSR (server.csr) created"

# --- Sign with CA ---
openssl x509 -req `
  -in "$CertsDir\server.csr" `
  -CA "$CertsDir\ca.pem" `
  -CAkey "$CertsDir\ca.key" `
  -CAcreateserial `
  -out "$CertsDir\cert.pem" `
  -days 365 -sha256 `
  -extensions v3_req `
  -extfile "$CertsDir\server.cnf"

Write-Host "==> Server certificate (cert.pem) signed by CA"
Write-Host ""
Write-Host "Files generated in ${CertsDir}:"
Get-ChildItem "$CertsDir" -Include *.pem,*.key,*.csr,*.srl,*.cnf -File | Format-Table Name, Length
Write-Host "Done. Traefik uses cert.pem and key.pem."
