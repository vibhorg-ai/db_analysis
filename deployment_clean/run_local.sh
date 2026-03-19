#!/usr/bin/env bash
# Run DB Analyzer AI v7 backend locally (Unix).
# Requires: Python 3.12+, dependencies installed, .env present.
# Usage: ./run_local.sh

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
if [ ! -f "$ROOT/.env" ]; then
  echo "Copy .env.template to .env and fill required values, then run again."
  exit 1
fi
export PYTHONPATH="$ROOT"
cd "$ROOT"
exec python run_api.py
