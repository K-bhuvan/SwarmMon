#!/usr/bin/env bash
# Onboard Mike's field fleet (robots auto-discover via ROS /swarmmon/fleet/status)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "${ROOT}/scripts/env.sh"
swarmmon_require_wsl_or_linux

BACKEND="${SWARMMON_BACKEND_URL:-http://localhost:8000}"
FLEET_ID="${SWARMMON_FLEET_ID:-mike-farm}"
FLEET_NAME="${SWARMMON_FLEET_NAME:-Mike agritech field fleet}"
ALERT_EMAIL="${SWARMMON_ALERT_EMAIL:-}"
OFFLINE_MIN="${SWARMMON_OFFLINE_ALERT_MINUTES:-5}"

curl -sf "${BACKEND}/health" >/dev/null || {
  echo "Start backend first: ./scripts/dev_backend.sh" >&2
  exit 1
}

payload="$(cat <<EOF
{
  "scenario_run_id": "${FLEET_ID}",
  "scenario_name": "${FLEET_NAME}",
  "notify_email": "${ALERT_EMAIL}",
  "offline_alert_minutes": ${OFFLINE_MIN},
  "robots": []
}
EOF
)"

echo "==> Onboarding fleet ${FLEET_ID} at ${BACKEND}"

response="$(curl -s -w $'\n%{http_code}' -X POST "${BACKEND}/api/v1/fleet/onboard" \
  -H "Content-Type: application/json" \
  -d "$payload")"

http_code="${response##*$'\n'}"
body="${response%$'\n'*}"

case "$http_code" in
  200)
    echo "$body" | python3 -m json.tool
    ;;
  409)
    echo "Onboard rejected (HTTP 409): fleet ID already used by a non-field scenario." >&2
    echo "$body" >&2
    exit 1
    ;;
  *)
    echo "Onboard failed (HTTP ${http_code}):" >&2
    echo "$body" >&2
    exit 1
    ;;
esac

echo ""
echo "Done. Next steps:"
echo "  1. Dashboard → Fleet → select ${FLEET_ID}"
echo "  2. Dashboard → Alerts → set email if not passed via SWARMMON_ALERT_EMAIL"
echo "  3. ROS (local dev with sample drones on topic):"
echo "       conda deactivate && ./scripts/ros2_mike_fleet.sh --dev"
echo "  4. ROS (production — real drones publish /swarmmon/fleet/status):"
echo "       conda deactivate && ./scripts/ros2_mike_fleet.sh"
echo ""
echo "See docs/fleet_ingest_standard.md"
