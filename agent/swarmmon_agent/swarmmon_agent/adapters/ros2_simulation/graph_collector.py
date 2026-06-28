from __future__ import annotations

from datetime import datetime
from typing import Any

try:
    import rclpy
    from rclpy.node import Node
except ImportError:  # pragma: no cover - optional ROS 2 dependency
    rclpy = None
    Node = object  # type: ignore[misc, assignment]


def _format_node_name(name: str, namespace: str) -> str:
    ns = namespace.rstrip("/")
    if ns:
        return f"{ns}/{name}".replace("//", "/")
    return name if name.startswith("/") else f"/{name}"


def _node_names(node: Node | None) -> list[str]:
    if rclpy is None or node is None:
        return []

    if hasattr(node, "get_node_names_and_namespaces"):
        return [
            _format_node_name(name, namespace)
            for name, namespace in node.get_node_names_and_namespaces()
        ]

    try:
        from rclpy.node import get_node_names  # older distros (Humble)

        return [name for name, _ns in get_node_names()]
    except ImportError:
        return []


class GraphCollector:
    """Collect ROS 2 node liveness as component_state events."""

    def __init__(
        self,
        node: Node,
        robot_id: str,
        scenario_run_id: str,
        required_nodes: list[str] | None = None,
    ) -> None:
        self.node = node
        self.robot_id = robot_id
        self.scenario_run_id = scenario_run_id
        self.required_nodes = required_nodes if required_nodes is not None else []

    def collect(self, timestamp: datetime) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        active_nodes = set(_node_names(self.node))
        normalized_active = {n.lstrip("/") for n in active_nodes}
        for node_name in self.required_nodes:
            status = "OK" if node_name.lstrip("/") in normalized_active or node_name in active_nodes else "MISSING"
            found = any(node_name.lstrip("/") in n for n in active_nodes)
            if found:
                status = "OK"
            events.append(
                {
                    "event_type": "component_state",
                    "robot_id": self.robot_id,
                    "scenario_run_id": self.scenario_run_id,
                    "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
                    "component_id": node_name,
                    "component_type": "ros2_node",
                    "status": status,
                }
            )
        return events
