#!/usr/bin/env bash
# Live ROS 2 demo: harness + fault runner + SwarmMon agent
# Requires: ROS 2 installed, backend on :8000
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_URL="${SWARMMON_BACKEND_URL:-http://localhost:8000}"
SCENARIO_RUN_ID="${SWARMMON_SCENARIO_RUN_ID:-run-ros2-live}"
ROBOT_ID="${SWARMMON_ROBOT_ID:-robot-01}"
VENV_DIR="${SWARMMON_ROS_VENV:-$ROOT/.venv-ros}"

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

swarmmon_export_ros_wsl_fixes() {
  export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-1}"
  if [[ -f "$ROOT/config/fastdds_wsl.xml" ]]; then
    export FASTRTPS_DEFAULT_PROFILES_FILE="$ROOT/config/fastdds_wsl.xml"
  fi
}

if ! source_ros; then
  echo "ROS 2 not found. Install ROS 2 or set ROS_SETUP, e.g.:"
  echo "  export ROS_SETUP=/opt/ros/jazzy/setup.bash"
  echo "  source \"\$ROS_SETUP\""
  exit 1
fi
swarmmon_export_ros_wsl_fixes

if [[ -n "${CONDA_DEFAULT_ENV:-}" ]]; then
  echo "Conda env '${CONDA_DEFAULT_ENV}' is active and usually blocks rclpy."
  echo "Run: conda deactivate"
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
  echo "rclpy not importable after sourcing ROS. Try:"
  echo "  source /opt/ros/${ROS_DISTRO:-jazzy}/setup.bash"
  exit 1
fi
echo "ROS Python: $ROS_PY ($(command -v "$ROS_PY")) ($ROS_DISTRO)"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "==> Creating ROS-linked venv at $VENV_DIR"
  "$ROS_PY" -m venv --system-site-packages "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
PY="$VENV_DIR/bin/python"

if ! "$PY" -c "import rclpy" 2>/dev/null; then
  echo "venv missing rclpy (system-site-packages). Recreate with:"
  echo "  rm -rf \"$VENV_DIR\" && ./scripts/ros2_live.sh"
  exit 1
fi

echo "==> Installing agent + fault-runner Python deps"
"$PY" -m pip install -q --upgrade pip
"$PY" -m pip install -q -e "$ROOT/agent/swarmmon_agent"

curl -sf "$BACKEND_URL/health" >/dev/null || {
  echo "Start backend first: cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000"
  exit 1
}

cleanup() {
  if [[ "${SWARMMON_CLEANUP_DONE:-0}" == "1" ]]; then
    return
  fi
  SWARMMON_CLEANUP_DONE=1
  echo "Stopping ROS 2 demo processes..."
  jobs -p | xargs -r kill 2>/dev/null || true
  wait 2>/dev/null || true
  echo "==> Marking scenario ${SCENARIO_RUN_ID} completed (dashboard clears live view)"
  curl -sf -X POST "${BACKEND_URL}/api/v1/scenarios/runs/${SCENARIO_RUN_ID}/complete" \
    -H "Content-Type: application/json" \
    -d "{}" >/dev/null || true
}
trap cleanup EXIT INT TERM

echo "==> Fault runner (background)"
"$PY" "$ROOT/simulation/fault_runner.py" \
  --backend-url "$BACKEND_URL" \
  --scenario-run-id "$SCENARIO_RUN_ID" \
  --scenario ros2_live_test \
  --no-ensure-run &
FAULT_PID=$!

sleep 1

echo "==> SwarmMon live stack — harness + agent in one process (Ctrl+C to stop)"
export SWARMMON_BACKEND_URL="$BACKEND_URL"
export SWARMMON_SCENARIO_RUN_ID="$SCENARIO_RUN_ID"
export SWARMMON_ROBOT_ID="$ROBOT_ID"
export SWARMMON_JSONL_PATH="$ROOT/examples/logs/${SCENARIO_RUN_ID}.jsonl"
export SWARMMON_SCENARIO_NAME="ros2_live_test"
mkdir -p "$ROOT/examples/logs"

"$PY" -m swarmmon_agent.adapters.ros2_simulation.live_stack \
  --fault sensor_rate_drop --fault-start 15 --fault-duration 10

echo "==> Scenario report"
curl -sf "$BACKEND_URL/api/v1/scenarios/runs/${SCENARIO_RUN_ID}/report" | "$PY" -m json.tool || true
