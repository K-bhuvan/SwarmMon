from __future__ import annotations

import signal
import sys
import threading
import time
from datetime import datetime, timezone

from swarmmon_agent.client import BackendClient, JsonlWriter, utc_now
from swarmmon_agent.config import AgentSettings
from swarmmon_agent.local_buffer import LocalBuffer

try:
    import rclpy
    from rclpy.executors import MultiThreadedExecutor
    from rclpy.node import Node

    from swarmmon_agent.adapters.ros2_simulation.diagnostics_collector import (
        DiagnosticsCollector,
    )
    from swarmmon_agent.adapters.ros2_simulation.graph_collector import GraphCollector
    from swarmmon_agent.adapters.ros2_simulation.topic_freshness import (
        TopicFreshnessCollector,
        TopicTracker,
    )

    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False


def _heartbeat(settings: AgentSettings, now: datetime) -> dict:
    return {
        "event_type": "heartbeat",
        "robot_id": settings.robot_id,
        "scenario_run_id": settings.scenario_run_id,
        "timestamp": now.isoformat().replace("+00:00", "Z"),
    }


def run_agent(settings: AgentSettings | None = None) -> int:
    if not ROS2_AVAILABLE:
        print(
            "ROS 2 (rclpy) is not available. Install ROS 2 and source the workspace, "
            "or use the lightweight publisher harness.",
            file=sys.stderr,
        )
        return 1

    settings = settings or AgentSettings()
    rclpy.init()
    node = Node("swarmmon_agent")
    client = BackendClient(settings)
    client.ensure_scenario_run()
    buffer = LocalBuffer()

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
        node, settings.robot_id, settings.scenario_run_id, trackers
    )
    graph_collector = GraphCollector(node, settings.robot_id, settings.scenario_run_id)
    diag_collector = DiagnosticsCollector(
        node, settings.robot_id, settings.scenario_run_id
    )

    running = True

    def shutdown(*_args: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    executor = MultiThreadedExecutor()
    executor.add_node(node)
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()

    # Allow DDS discovery + first messages before reporting freshness.
    time.sleep(1.0)

    with JsonlWriter(settings.jsonl_path) as jsonl:
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

        client.send_batch(buffer.drain(settings.batch_size))
        client.complete_run()

    executor.shutdown()
    spin_thread.join(timeout=2.0)
    node.destroy_node()
    rclpy.shutdown()
    return 0


def main() -> None:
    raise SystemExit(run_agent())


if __name__ == "__main__":
    main()
