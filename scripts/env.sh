#!/usr/bin/env bash
# Shared SwarmMon dev environment — source from other scripts:
#   source "$(dirname "$0")/env.sh"
set -euo pipefail

export SWARMMON_REPO="${SWARMMON_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
export SWARMMON_BACKEND_URL="${SWARMMON_BACKEND_URL:-http://localhost:8000}"
export SWARMMON_SCENARIO_RUN_ID="${SWARMMON_SCENARIO_RUN_ID:-run-ros2-live}"

# ROS 2 Jazzy on this machine (override with ROS_SETUP if needed)
export ROS_SETUP="${ROS_SETUP:-/opt/ros/jazzy/setup.bash}"

swarmmon_require_wsl_or_linux() {
  if [[ "$(uname -s)" != "Linux" ]]; then
    echo "SwarmMon dev scripts require Linux or WSL." >&2
    echo "On Windows, open an Ubuntu (WSL) terminal — do not use PowerShell for npm/python/ROS." >&2
    exit 1
  fi
}

swarmmon_activate_backend_env() {
  if [[ -n "${CONDA_DEFAULT_ENV:-}" ]]; then
    echo "Using conda env: ${CONDA_DEFAULT_ENV}"
    return 0
  fi
  if command -v conda >/dev/null 2>&1; then
    # shellcheck disable=SC1091
    source "$(conda info --base)/etc/profile.d/conda.sh"
    conda activate swarmmon
    echo "Activated conda env: swarmmon"
    return 0
  fi
  if [[ -f "${SWARMMON_REPO}/backend/.venv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "${SWARMMON_REPO}/backend/.venv/bin/activate"
    echo "Activated backend/.venv"
    return 0
  fi
  echo "No Python env found. Run: ./scripts/setup.sh" >&2
  exit 1
}

swarmmon_source_ros() {
  if [[ -n "${ROS_DISTRO:-}" ]]; then
    return 0
  fi
  if [[ -f "${ROS_SETUP}" ]]; then
    # shellcheck disable=SC1090
    source "${ROS_SETUP}"
    return 0
  fi
  echo "ROS 2 not found at ${ROS_SETUP}. Install ROS 2 or set ROS_SETUP." >&2
  exit 1
}

swarmmon_require_linux_node() {
  if command -v node >/dev/null 2>&1 && [[ "$(node -p 'process.platform')" == "linux" ]]; then
    return 0
  fi
  echo "ERROR: WSL is using Windows Node.js (or Node is missing)." >&2
  echo "  which npm -> $(command -v npm 2>/dev/null || echo 'not found')" >&2
  echo "" >&2
  echo "Install Node inside WSL, then open a new terminal:" >&2
  echo "  ./scripts/setup.sh" >&2
  echo "" >&2
  echo "Or manually (nvm):" >&2
  echo "  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash" >&2
  echo "  source ~/.nvm/nvm.sh && nvm install 20" >&2
  exit 1
}

swarmmon_install_linux_node() {
  if command -v node >/dev/null 2>&1 && [[ "$(node -p 'process.platform')" == "linux" ]]; then
    echo "Linux Node.js already installed: $(node -v)"
    return 0
  fi
  echo "==> Installing Node.js 20 in WSL (nvm)…"
  export NVM_DIR="${HOME}/.nvm"
  if [[ ! -s "${NVM_DIR}/nvm.sh" ]]; then
    curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
  fi
  # shellcheck disable=SC1091
  source "${NVM_DIR}/nvm.sh"
  nvm install 20
  nvm alias default 20
  echo "Node: $(command -v node) ($(node -v))"
}

swarmmon_check_backend() {
  curl -sf "${SWARMMON_BACKEND_URL}/health" >/dev/null
}

swarmmon_dashboard_linux_ready() {
  [[ -d "${SWARMMON_REPO}/dashboard/node_modules/@rollup/rollup-linux-x64-gnu" ]]
}

swarmmon_repair_dashboard_deps() {
  swarmmon_require_linux_node
  local dash="${SWARMMON_REPO}/dashboard"
  echo "==> Repairing dashboard npm packages for Linux/WSL…"

  if [[ -d "${dash}/node_modules" ]]; then
    if ! rm -rf "${dash}/node_modules" 2>/dev/null; then
      echo "==> WSL cannot delete Windows-locked node_modules; using PowerShell…"
      if ! command -v powershell.exe >/dev/null 2>&1 && ! command -v pwsh.exe >/dev/null 2>&1; then
        echo "Delete dashboard/node_modules from Windows, then run: cd dashboard && npm install" >&2
        exit 1
      fi
      local win_path
      win_path=$(wslpath -w "${dash}/node_modules")
      if ! powershell.exe -NoProfile -Command "Get-Process node -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue; Start-Sleep -Seconds 1; Remove-Item -LiteralPath '${win_path}' -Recurse -Force -ErrorAction Stop"; then
        echo "Could not remove node_modules. Close any running 'npm run dev' / Vite windows, then retry." >&2
        exit 1
      fi
    fi
  fi

  (cd "$dash" && npm install)
  touch "${dash}/node_modules/.swarmmon-linux-deps"
}

swarmmon_ensure_dashboard_deps() {
  if swarmmon_dashboard_linux_ready; then
    return 0
  fi
  swarmmon_repair_dashboard_deps
}
