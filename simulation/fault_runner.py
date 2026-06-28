#!/usr/bin/env python3
"""
Schedule scenario faults by posting fault_injected events to the SwarmMon backend.

Use alongside ROS 2 harness + agent for live fault → incident → report validation.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCENARIOS_DIR = REPO_ROOT / "simulation" / "scenarios"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Schedule SwarmMon scenario fault injections")
    p.add_argument(
        "--scenario",
        default="ros2_live_test",
        help="Scenario YAML name (without path) or full path",
    )
    p.add_argument("--scenario-run-id", default="run-ros2-live")
    p.add_argument("--backend-url", default="http://localhost:8000")
    p.add_argument(
        "--scenarios-dir",
        type=Path,
        default=DEFAULT_SCENARIOS_DIR,
    )
    p.add_argument(
        "--ensure-run",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Create scenario run from YAML before scheduling faults",
    )
    return p.parse_args()


def resolve_path(scenarios_dir: Path, scenario: str) -> Path:
    candidate = Path(scenario)
    if candidate.is_file():
        return candidate
    for name in (f"{scenario}.yaml", f"{scenario}.yml"):
        path = scenarios_dir / name
        if path.is_file():
            return path
    raise FileNotFoundError(f"Scenario not found: {scenario}")


def fault_delay_seconds(fault: dict) -> float:
    if "start_after_seconds" in fault:
        return float(fault["start_after_seconds"])
    if "start_minute" in fault:
        return float(fault["start_minute"]) * 60.0
    return 0.0


def fault_message(fault: dict) -> str:
    if msg := fault.get("message"):
        return msg
    signal = fault.get("signal_id", "")
    ftype = fault.get("type", "unknown")
    if signal:
        return f"fault injected: {ftype} on {signal}"
    return f"fault injected: {ftype}"


def ensure_scenario_run(client: httpx.Client, base: str, run_id: str, scenario_name: str) -> None:
    resp = client.post(
        f"{base}/api/v1/scenarios/runs/from-yaml",
        json={"scenario_run_id": run_id, "scenario_name": scenario_name},
    )
    if resp.status_code == 409:
        client.post(f"{base}/api/v1/scenarios/runs/{run_id}/reset").raise_for_status()
        print(f"Reset existing scenario run {run_id}")
    elif resp.status_code >= 400:
        resp.raise_for_status()
    else:
        print(f"Created scenario run {run_id} from {scenario_name}")


def inject_fault(
    client: httpx.Client,
    base: str,
    scenario_run_id: str,
    fault: dict,
) -> None:
    robots = fault.get("affected_robots") or ["robot-01"]
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    events = [
        {
            "event_type": "fault_injected",
            "robot_id": robot_id,
            "scenario_run_id": scenario_run_id,
            "timestamp": now,
            "fault_type": fault.get("type", "unknown"),
            "signal_id": fault.get("signal_id"),
            "message": fault_message(fault),
        }
        for robot_id in robots
    ]
    client.post(f"{base}/api/v1/events/batch", json={"events": events}).raise_for_status()
    print(f"Injected fault: {fault_message(fault)} -> {', '.join(robots)}")


def main() -> int:
    args = parse_args()
    base = args.backend_url.rstrip("/")

    try:
        path = resolve_path(args.scenarios_dir, args.scenario)
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError, OSError) as exc:
        print(f"Error loading scenario: {exc}", file=sys.stderr)
        return 1

    faults = sorted(data.get("faults", []), key=fault_delay_seconds)
    scenario_name = data.get("scenario", {}).get("name", args.scenario)

    with httpx.Client(timeout=30.0) as client:
        client.get(f"{base}/health").raise_for_status()
        if args.ensure_run:
            ensure_scenario_run(client, base, args.scenario_run_id, scenario_name)

        if not faults:
            print("No faults defined in scenario.")
            return 0

        t0 = time.monotonic()
        print(f"Scheduling {len(faults)} fault(s) for scenario run {args.scenario_run_id}")
        for fault in faults:
            delay = fault_delay_seconds(fault)
            elapsed = time.monotonic() - t0
            wait = delay - elapsed
            if wait > 0:
                print(f"Waiting {wait:.1f}s until fault: {fault.get('type')}")
                time.sleep(wait)
            inject_fault(client, base, args.scenario_run_id, fault)

        print("All faults injected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
