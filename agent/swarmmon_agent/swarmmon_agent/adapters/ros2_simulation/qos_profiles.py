"""Shared ROS 2 QoS profiles for harness <-> agent topic matching."""

from __future__ import annotations

try:
    from rclpy.qos import (
        DurabilityPolicy,
        HistoryPolicy,
        QoSProfile,
        ReliabilityPolicy,
        qos_profile_sensor_data,
    )
except ImportError:  # pragma: no cover
    QoSProfile = None  # type: ignore[misc, assignment]
    qos_profile_sensor_data = None

# Reliable pub/sub — works for harness demo (scan + odom + diagnostics).
SIM_TOPIC_QOS = (
    QoSProfile(
        reliability=ReliabilityPolicy.RELIABLE,
        history=HistoryPolicy.KEEP_LAST,
        depth=10,
        durability=DurabilityPolicy.VOLATILE,
    )
    if QoSProfile is not None
    else None
)

# LaserScan often uses sensor QoS in production; keep for reference.
SENSOR_TOPIC_QOS = qos_profile_sensor_data
