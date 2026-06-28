from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

try:
    import rclpy
    from rclpy.node import Node
    from nav_msgs.msg import Odometry
    from sensor_msgs.msg import LaserScan

    from swarmmon_agent.adapters.ros2_simulation.qos_profiles import SIM_TOPIC_QOS
except ImportError:  # pragma: no cover
    rclpy = None
    Node = object  # type: ignore[misc, assignment]
    SIM_TOPIC_QOS = None
    DiagnosticArray = Odometry = LaserScan = None


@dataclass
class TopicTracker:
    topic: str
    message_type: str
    expected_rate_hz: float
    stale_after_ms: int
    last_seen: datetime | None = None
    message_count: int = 0

    def record(self, now: datetime) -> None:
        self.last_seen = now
        self.message_count += 1

    def freshness_event(
        self, robot_id: str, scenario_run_id: str, now: datetime
    ) -> dict[str, Any]:
        if self.last_seen is None:
            status = "MISSING"
            last_seen_ms = 999_999
        else:
            last_seen_ms = int((now - self.last_seen).total_seconds() * 1000)
            status = "STALE" if last_seen_ms > self.stale_after_ms else "OK"
        return {
            "event_type": "signal_freshness",
            "robot_id": robot_id,
            "scenario_run_id": scenario_run_id,
            "timestamp": now.isoformat().replace("+00:00", "Z"),
            "signal_id": self.topic,
            "signal_type": "ros2_topic",
            "message_type": self.message_type,
            "expected_rate_hz": self.expected_rate_hz,
            "last_seen_ms_ago": last_seen_ms,
            "status": status,
        }


class TopicFreshnessCollector:
    """Subscribe to ROS 2 topics and emit signal_freshness events."""

    def __init__(
        self,
        node: Node,
        robot_id: str,
        scenario_run_id: str,
        trackers: list[TopicTracker],
    ) -> None:
        self.node = node
        self.robot_id = robot_id
        self.scenario_run_id = scenario_run_id
        self.trackers = {t.topic: t for t in trackers}
        if rclpy is None:
            return
        for topic, tracker in self.trackers.items():
            if topic.endswith("scan") or topic == "/scan":
                node.create_subscription(
                    LaserScan,
                    topic,
                    lambda _msg, t=tracker: self._on_message(t),
                    SIM_TOPIC_QOS,
                )
            elif "odom" in topic:
                node.create_subscription(
                    Odometry,
                    topic,
                    lambda _msg, t=tracker: self._on_message(t),
                    SIM_TOPIC_QOS,
                )

    def _on_message(self, tracker: TopicTracker) -> None:
        tracker.record(datetime.now(timezone.utc))

    def collect(self, now: datetime) -> list[dict[str, Any]]:
        return [
            t.freshness_event(self.robot_id, self.scenario_run_id, now)
            for t in self.trackers.values()
        ]
