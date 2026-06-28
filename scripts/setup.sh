#!/usr/bin/env bash
# One-time setup — run inside WSL from repo root: ./scripts/setup.sh
set -euo pipefail
source "$(dirname "$0")/env.sh"
swarmmon_require_wsl_or_linux

echo "==> SwarmMon setup (WSL/Linux)"
echo "    Repo: ${SWARMMON_REPO}"

# Backend Python
if command -v conda >/dev/null 2>&1; then
  if ! conda env list | grep -q '^swarmmon '; then
    echo "==> Creating conda env swarmmon (Python 3.11)"
    conda create -n swarmmon python=3.11 -y
  fi
  # shellcheck disable=SC1091
  source "$(conda info --base)/etc/profile.d/conda.sh"
  conda activate swarmmon
else
  echo "==> Creating backend/.venv (no conda found)"
  python3 -m venv "${SWARMMON_REPO}/backend/.venv"
  # shellcheck disable=SC1091
  source "${SWARMMON_REPO}/backend/.venv/bin/activate"
fi

pip install -q --upgrade pip
pip install -q -e "${SWARMMON_REPO}/backend[dev]"

# Dashboard — Linux Node.js required (not Windows /mnt/c/Program Files/nodejs)
swarmmon_install_linux_node
echo "==> Dashboard npm install"
swarmmon_repair_dashboard_deps

# ROS live venv is created on first ./scripts/ros2_live.sh run
if [[ -f "${ROS_SETUP}" ]]; then
  echo "==> ROS 2 found: ${ROS_SETUP}"
else
  echo "==> ROS 2 not at ${ROS_SETUP} — install for live demo (optional)"
fi

echo ""
echo "Setup complete. Use three WSL terminals:"
echo "  1. ./scripts/dev_backend.sh"
echo "  2. ./scripts/dev_dashboard.sh"
echo "  3. conda deactivate && ./scripts/ros2_live.sh"
echo ""
echo "See docs/dev_environment.md"
