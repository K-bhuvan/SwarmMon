# ROS 2 live harness demo

Single-robot observability: heartbeats, `/scan`, `/odom`, timed faults → incidents → scenario report. **Not** the Mike field-fleet path ([README](../README.md#example-mikes-farm)).

## Quick start

Environment setup: [dev_environment.md](dev_environment.md). Then:

```bash
conda deactivate && ./scripts/ros2_live.sh
```

Dashboard scenario: **`run-ros2-live`**.

The script starts the harness, fault runner (`simulation/scenarios/ros2_live_test.yaml`), and agent together.

## What to expect

| Time | Event |
|------|-------|
| 0s | Agent streams heartbeats, `/scan`, `/odom`, diagnostics |
| ~15s | Harness drops `/scan` rate; fault runner posts `fault_injected` |
| ~17s | Agent reports `STALE` for `/scan` → incident opens |
| ~25s | `/scan` recovers → incident closes |

Verify: Fleet page (robot-01 WARN then OK) · Incidents page · `GET /api/v1/scenarios/runs/run-ros2-live/report`

## Manual split (advanced)

If you need separate terminals instead of `ros2_live.sh`:

**Harness**

```bash
source /opt/ros/jazzy/setup.bash   # or humble
python agent/swarmmon_agent/swarmmon_agent/adapters/ros2_simulation/ros2_harness.py \
  --fault sensor_rate_drop --fault-start 15 --fault-duration 10
```

**Fault runner**

```bash
python simulation/fault_runner.py --scenario-run-id run-ros2-live --scenario ros2_live_test
```

**Agent**

```bash
export SWARMMON_BACKEND_URL=http://localhost:8000
export SWARMMON_SCENARIO_RUN_ID=run-ros2-live
export SWARMMON_ROBOT_ID=robot-01
export SWARMMON_SCENARIO_NAME=ros2_live_test
swarmmon-agent
```

Agent JSONL artifacts (optional): `examples/logs/run-ros2-live.jsonl` (gitignored).
