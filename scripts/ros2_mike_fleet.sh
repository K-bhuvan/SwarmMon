#!/usr/bin/env bash
# Mike field fleet — ROS topic /swarmmon/fleet/status → SwarmMon backend
# Local dev: add --dev to publish sample drone status on the same ROS topic
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_URL="${SWARMMON_BACKEND_URL:-http://localhost:8000}"
FLEET_ID="${SWARMMON_FLEET_ID:-mike-farm}"
VENV_DIR="${SWARMMON_ROS_VENV:-$ROOT/.venv-ros}"
DEV_MODE=0

for arg in "$@"; do
  case "$arg" in
    --dev) DEV_MODE=1 ;;
  esac
done

source_ros() {
  if [[ -n "${ROS_DISTRO:-}" ]]; then
    return 0
  fi
  if [[ -n "${ROS_SETUP:-}" && -f "$ROS_SETUP" ]]; then
    # shellcheck disable=SC1090
    source "$ROS_SETUP"
    return 0
  fi
  for setup in \
    /opt/ros/jazzy/setup.bash \
    /opt/ros/humble/setup.bash \
    /opt/ros/iron/setup.bash \
    /opt/ros/*/setup.bash; do
    if [[ -f "$setup" ]]; then
      # shellcheck disable=SC1090
      source "$setup"
      echo "Sourced ROS 2: $ROS_DISTRO ($setup)"
      return 0
    fi
  done
  return 1
}

if ! source_ros; then
  echo "ROS 2 not found. Install ROS 2 or set ROS_SETUP." >&2
  exit 1
fi

export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-1}"
if [[ -f "$ROOT/config/fastdds_wsl.xml" ]]; then
  export FASTRTPS_DEFAULT_PROFILES_FILE="$ROOT/config/fastdds_wsl.xml"
fi

if [[ -n "${CONDA_DEFAULT_ENV:-}" ]]; then
  echo "Conda env '${CONDA_DEFAULT_ENV}' blocks rclpy. Run: conda deactivate" >&2
  exit 1
fi

ROS_PY=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null && "$candidate" -c "import rclpy" 2>/dev/null; then
    ROS_PY="$candidate"
    break
  fi
done
if [[ -z "$ROS_PY" ]]; then
  echo "rclpy not importable after sourcing ROS." >&2
  exit 1
fi

if [[ ! -d "$VENV_DIR" ]]; then
  echo "==> Creating ROS-linked venv at $VENV_DIR"
  "$ROS_PY" -m venv --system-site-packages "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
PY="$VENV_DIR/bin/python"

"$PY" -m pip install -q --upgrade pip
"$PY" -m pip install -q -e "$ROOT/agent/swarmmon_agent"

curl -sf "$BACKEND_URL/health" >/dev/null || {
  echo "Start backend first: ./scripts/dev_backend.sh" >&2
  exit 1
}

echo "==> Fleet ${FLEET_ID} — gateway on /swarmmon/fleet/status → ${BACKEND_URL}"
if [[ "$DEV_MODE" == "1" ]]; then
  echo "    --dev: publishing ${SWARMMON_DRONE_COUNT:-4} drones on ROS topic (local only)"
  echo "    Onboard first if needed: ./scripts/onboard_field_fleet.sh"
else
  echo "    Production mode: waiting for drones on /swarmmon/fleet/status"
  echo "    Onboard first: ./scripts/onboard_field_fleet.sh"
fi

export SWARMMON_BACKEND_URL="$BACKEND_URL"
export SWARMMON_FLEET_ID="$FLEET_ID"

STACK_ARGS=()
if [[ "$DEV_MODE" == "1" ]]; then
  STACK_ARGS+=(--dev)
fi

exec "$PY" -m swarmmon_agent.adapters.ros2_simulation.field_fleet_stack "${STACK_ARGS[@]}"
