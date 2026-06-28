"""ROS 2 fleet gateway — subscribe /swarmmon/fleet/status, forward to SwarmMon backend."""

from __future__ import annotations

import json
import os

import httpx
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from swarmmon_agent.adapters.ros2_simulation.fleet_constants import FLEET_STATUS_TOPIC


class FleetGateway(Node):
    def __init__(self) -> None:
        super().__init__("swarmmon_fleet_gateway")
        backend = os.environ.get("SWARMMON_BACKEND_URL", "http://localhost:8000").rstrip("/")
        topic = os.environ.get("SWARMMON_FLEET_STATUS_TOPIC", FLEET_STATUS_TOPIC)
        api_key = os.environ.get("SWARMMON_INGEST_API_KEY", "")
        self._backend = backend
        self._api_key = api_key
        self._client = httpx.Client(timeout=30.0)
        self._client.get(f"{backend}/health").raise_for_status()
        self.create_subscription(String, topic, self._on_status, 10)
        self.get_logger().info(f"Forwarding {topic} → {backend}/api/v1/fleet/ingest")

    def _on_status(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError as exc:
            self.get_logger().error(f"Invalid JSON on fleet topic: {exc}")
            return
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["X-SwarmMon-Key"] = self._api_key
        try:
            resp = self._client.post(
                f"{self._backend}/api/v1/fleet/ingest",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            body = resp.json()
            self.get_logger().info(
                f"ingest ok: robots={body.get('robots_seen')} "
                f"registered={body.get('registered')}"
            )
        except httpx.HTTPError as exc:
            self.get_logger().error(f"ingest failed: {exc}")

    def destroy_node(self) -> bool:
        self._client.close()
        return super().destroy_node()
