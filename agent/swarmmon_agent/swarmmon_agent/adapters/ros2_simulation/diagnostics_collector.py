from __future__ import annotations

from datetime import datetime
from typing import Any

try:
    import rclpy
    from rclpy.node import Node
    from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus

    from swarmmon_agent.adapters.ros2_simulation.qos_profiles import SIM_TOPIC_QOS
except ImportError:  # pragma: no cover
    rclpy = None
    Node = object  # type: ignore[misc, assignment]
    SIM_TOPIC_QOS = None
    DiagnosticArray = DiagnosticStatus = None

_LEVEL_MAP = {0: "OK", 1: "WARN", 2: "ERROR", 3: "ERROR"}


class DiagnosticsCollector:
    def __init__(
        self,
        node: Node,
        robot_id: str,
        scenario_run_id: str,
        topic: str = "/diagnostics",
    ) -> None:
        self.robot_id = robot_id
        self.scenario_run_id = scenario_run_id
        self._latest: list[dict[str, Any]] = []
        if rclpy is None:
            return
        node.create_subscription(DiagnosticArray, topic, self._on_diagnostics, SIM_TOPIC_QOS)

    def _on_diagnostics(self, msg: DiagnosticArray) -> None:
        now = datetime.utcnow()
        self._latest = [
            {
                "event_type": "diagnostic",
                "robot_id": self.robot_id,
                "scenario_run_id": self.scenario_run_id,
                "timestamp": now.isoformat().replace("+00:00", "Z"),
                "name": status.name,
                "level": _LEVEL_MAP.get(status.level, "OK"),
                "message": status.message,
            }
            for status in msg.status
        ]

    def collect(self) -> list[dict[str, Any]]:
        return list(self._latest)
