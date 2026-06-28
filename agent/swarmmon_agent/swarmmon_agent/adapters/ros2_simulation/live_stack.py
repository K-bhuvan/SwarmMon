#!/usr/bin/env python3
"""
Run harness + SwarmMon agent in one ROS 2 process (reliable on WSL).

Separate processes often fail DDS discovery on WSL; one rclpy context fixes /scan /odom.
Fault runner stays a separate HTTP sidecar (started by ros2_live.sh).
"""

from __future__ import annotations

import argparse
import signal
import sys
import threading
import time

import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from swarmmon_agent.adapters.ros2_simulation.diagnostics_collector import (
    DiagnosticsCollector,
)
from swarmmon_agent.adapters.ros2_simulation.graph_collector import GraphCollector
from swarmmon_agent.adapters.ros2_simulation.ros2_harness import SimHarness
from swarmmon_agent.adapters.ros2_simulation.topic_freshness import (
    TopicFreshnessCollector,
    TopicTracker,
)
from swarmmon_agent.client import BackendClient, JsonlWriter, utc_now
from swarmmon_agent.config import AgentSettings
from swarmmon_agent.local_buffer import LocalBuffer
from swarmmon_agent.main import _heartbeat


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="SwarmMon live stack (harness + agent)")
    p.add_argument("--scan-hz", type=float, default=10.0)
    p.add_argument("--odom-hz", type=float, default=30.0)
    p.add_argument("--diag-hz", type=float, default=1.0)
    p.add_argument("--fault", choices=["sensor_rate_drop"], default="sensor_rate_drop")
    p.add_argument("--fault-start", type=float, default=15.0)
    p.add_argument("--fault-duration", type=float, default=10.0)
    return p.parse_args()


def run_live_stack(settings: AgentSettings | None = None, harness_args: argparse.Namespace | None = None) -> int:
    settings = settings or AgentSettings()
    harness_args = harness_args or parse_args()

    client = BackendClient(settings)
    client.ensure_scenario_run()
    buffer = LocalBuffer()

    rclpy.init()
    executor = MultiThreadedExecutor()

    harness = SimHarness(harness_args)
    agent_node = Node("swarmmon_agent")
    executor.add_node(harness)
    executor.add_node(agent_node)

    trackers = [
        TopicTracker(
            topic=settings.scan_topic,
            message_type="sensor_msgs/msg/LaserScan",
            expected_rate_hz=settings.scan_expected_hz,
            stale_after_ms=settings.scan_stale_ms,
        ),
        TopicTracker(
            topic=settings.odom_topic,
            message_type="nav_msgs/msg/Odometry",
            expected_rate_hz=settings.odom_expected_hz,
            stale_after_ms=settings.odom_stale_ms,
        ),
    ]
    topic_collector = TopicFreshnessCollector(
        agent_node, settings.robot_id, settings.scenario_run_id, trackers
    )
    graph_collector = GraphCollector(agent_node, settings.robot_id, settings.scenario_run_id)
    diag_collector = DiagnosticsCollector(
        agent_node, settings.robot_id, settings.scenario_run_id
    )

    running = True

    def shutdown(*_args: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()
    time.sleep(1.0)

    print(
        f"Live stack running: robot={settings.robot_id} scenario={settings.scenario_run_id}",
        file=sys.stderr,
    )

    with JsonlWriter(settings.jsonl_path) as jsonl:
        try:
            while running and rclpy.ok():
                time.sleep(settings.poll_interval_seconds)
                now = utc_now()
                events = [
                    _heartbeat(settings, now),
                    *graph_collector.collect(now),
                    *topic_collector.collect(now),
                    *diag_collector.collect(),
                ]
                for event in events:
                    buffer.add(event)
                    jsonl.write(event)

                batch = buffer.drain(settings.batch_size)
                if batch:
                    client.send_batch(batch)
        finally:
            client.send_batch(buffer.drain(settings.batch_size))
            client.complete_run()
            print(
                f"Scenario {settings.scenario_run_id} completed (live stream ended).",
                file=sys.stderr,
            )

    executor.shutdown()
    spin_thread.join(timeout=2.0)
    harness.destroy_node()
    agent_node.destroy_node()
    rclpy.shutdown()
    return 0


def main() -> int:
    return run_live_stack(harness_args=parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
