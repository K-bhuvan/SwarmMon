"""
Local dev: publish Mike-style fleet snapshots on /swarmmon/fleet/status.

Real drones (or a farm aggregator) publish the same topic in production.
"""

from __future__ import annotations

import json
import os
import random
from datetime import datetime, timezone

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from swarmmon_agent.adapters.ros2_simulation.fleet_constants import (
    FLEET_INGEST_SCHEMA_VERSION,
    FLEET_STATUS_TOPIC,
)

MIKE_LABELS = ("North field", "South field", "East field", "West field")


class FleetStatusPublisher(Node):
    """Publishes schema v1 fleet JSON to the standard ROS topic."""

    def __init__(
        self,
        *,
        fleet_id: str,
        drone_count: int,
        interval_seconds: float,
    ) -> None:
        super().__init__("swarmmon_fleet_status_publisher")
        topic = os.environ.get("SWARMMON_FLEET_STATUS_TOPIC", FLEET_STATUS_TOPIC)
        self._fleet_id = fleet_id
        self._drone_count = max(1, drone_count)
        self._pub = self.create_publisher(String, topic, 10)
        self.create_timer(interval_seconds, self._publish)
        self.get_logger().info(
            f"Publishing {self._drone_count} drones on {topic} (fleet={fleet_id})"
        )

    def _publish(self) -> None:
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        robots = []
        for i in range(1, self._drone_count + 1):
            robot_id = f"drone-{i:02d}"
            label = MIKE_LABELS[i - 1] if i <= len(MIKE_LABELS) else f"Field unit {i}"
            robots.append(
                {
                    "robot_id": robot_id,
                    "label": label,
                    "online": True,
                    "battery_pct": round(random.uniform(40, 98), 1),
                }
            )
        payload = {
            "schema_version": FLEET_INGEST_SCHEMA_VERSION,
            "fleet_id": self._fleet_id,
            "timestamp": ts,
            "robots": robots,
        }
        msg = String()
        msg.data = json.dumps(payload)
        self._pub.publish(msg)
