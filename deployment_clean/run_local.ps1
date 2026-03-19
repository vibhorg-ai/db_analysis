# Run DB Analyzer AI v7 backend locally (Windows).
# Requires: Python 3.12+, dependencies installed, .env present.
# Usage: .\run_local.ps1

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
if (-not (Test-Path "$Root\.env")) {
    Write-Host "Copy .env.template to .env and fill required values, then run again."
    exit 1
}
$env:PYTHONPATH = $Root
Set-Location $Root
python run_api.py
