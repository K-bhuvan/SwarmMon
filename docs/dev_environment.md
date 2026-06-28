# Development environment

SwarmMon runs on **Linux** (Ubuntu 22.04 / 24.04) or **WSL2**. Use an **Ubuntu (WSL) terminal** — not Windows PowerShell — for all scripts.

**First run:** [README](../README.md#example-mikes-farm) (Mike field fleet) or [ros2_live.md](ros2_live.md) (single-robot harness).

## One-time setup

```bash
cd ~/projects/SwarmMon
chmod +x scripts/*.sh
./scripts/setup.sh
```

## Platform pitfalls (WSL)

| Do on Linux / WSL | Avoid |
|-------------------|--------|
| `npm install` / `./scripts/dev_dashboard.sh` | PowerShell `npm` (breaks WSL `node_modules`) |
| `backend/.venv` or conda `swarmmon` | `backend\.venv\Scripts\` (Windows venv) |
| `./scripts/ros2_*.sh` after `conda deactivate` | Running ROS scripts with conda active |

`node_modules` and Python venvs are **platform-specific**. Mixing Windows and WSL installs breaks Rollup, `rclpy`, and paths.

## Runtime cheat sheet

| Component | Environment | Typical scenario |
|-----------|-------------|------------------|
| Backend | conda `swarmmon` or `backend/.venv` | — |
| Dashboard | Node 20+ (nvm or system) | auto-picks `running` |
| Field fleet | `.venv-ros` + gateway | `mike-farm` |
| ROS harness | `.venv-ros` | `run-ros2-live` |

## If something breaks

**`node: command not found` or wrong Rollup arch**

```bash
./scripts/setup.sh
source ~/.nvm/nvm.sh
node -p process.platform   # must print: linux
./scripts/dev_dashboard.sh
```

**`rclpy` not found**

```bash
conda deactivate
./scripts/ros2_live.sh    # or ros2_mike_fleet.sh
```

**Dashboard empty but ROS is running**

- Fleet dropdown: **`mike-farm`** or **`run-ros2-live`**
- Backend: `curl http://localhost:8000/health`
