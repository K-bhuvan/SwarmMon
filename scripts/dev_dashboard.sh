#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/env.sh"
swarmmon_require_wsl_or_linux

# nvm is installed per-shell; load if present
if [[ -s "${HOME}/.nvm/nvm.sh" ]]; then
  # shellcheck disable=SC1091
  source "${HOME}/.nvm/nvm.sh"
fi
swarmmon_require_linux_node
swarmmon_ensure_dashboard_deps

cd "${SWARMMON_REPO}/dashboard"
DASHBOARD_PORT="${SWARMMON_DASHBOARD_PORT:-5173}"

if command -v fuser >/dev/null 2>&1 && fuser "${DASHBOARD_PORT}/tcp" >/dev/null 2>&1; then
  echo "WARNING: port ${DASHBOARD_PORT} is already in use (stale dashboard?)." >&2
  echo "  Stop it: fuser -k ${DASHBOARD_PORT}/tcp" >&2
  echo "  Or use another port: SWARMMON_DASHBOARD_PORT=5174 ./scripts/dev_dashboard.sh" >&2
fi

echo "==> Dashboard http://localhost:${DASHBOARD_PORT}"
echo "    API proxy -> ${SWARMMON_BACKEND_URL}"
exec npm run dev -- --host 0.0.0.0 --port "${DASHBOARD_PORT}" --strictPort
