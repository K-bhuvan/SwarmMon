#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/env.sh"
swarmmon_require_wsl_or_linux
swarmmon_activate_backend_env

cd "${SWARMMON_REPO}/backend"
echo "==> Backend http://0.0.0.0:8000  (health: ${SWARMMON_BACKEND_URL}/health)"
exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
