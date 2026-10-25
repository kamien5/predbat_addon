#!/usr/bin/env bash
set -euo pipefail
echo "Running Predbat inside Add-on (kamien5 fork)"
for v in $(compgen -e | grep '^PREDBAT_' || true); do unset "$v"; done
exec python3 /startup.py
