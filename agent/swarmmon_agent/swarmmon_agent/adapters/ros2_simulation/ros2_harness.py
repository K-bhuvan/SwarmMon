#!/usr/bin/env python3
"""
Lightweight ROS 2 publisher harness for SwarmMon agent development.

Publishes /scan, /odom, and /diagnostics at configured rates without Isaac Sim.
Supports timed fault injection (sensor rate drop).

Usage (after sourcing ROS 2):
  python ros2_harness.py
  python ros2_harness.py --fault sensor_rate_drop --fault-start 10 --fault-duration 5
"""

from __future__ import annotations

import argparse
import math
import sys
import time

try:
    import rclpy
    from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
    from nav_msgs.msg import Odometry
    from rclpy.node import Node
    from sensor_msgs.msg import LaserScan

    from swarmmon_agent.adapters.ros2_simulation.qos_profiles import SIM_TOPIC_QOS
except ImportError:
    print("ROS 2 (rclpy) required. Source your ROS 2 installation first.", file=sys.stderr)
    raise SystemExit(1)


class SimHarness(Node):
    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__("swarmmon_sim_harness")
        self.args = args
        self._scan_pub = self.create_publisher(LaserScan, "/scan", SIM_TOPIC_QOS)
        self._odom_pub = self.create_publisher(Odometry, "/odom", SIM_TOPIC_QOS)
        self._diag_pub = self.create_publisher(DiagnosticArray, "/diagnostics", SIM_TOPIC_QOS)
        self._start = time.monotonic()
        self._scan_enabled = True
        scan_period = 1.0 / args.scan_hz
        odom_period = 1.0 / args.odom_hz
        diag_period = 1.0 / args.diag_hz
        self.create_timer(scan_period, self._publish_scan)
        self.create_timer(odom_period, self._publish_odom)
        self.create_timer(diag_period, self._publish_diagnostics)
        if args.fault:
            self.create_timer(0.5, self._check_fault)

    def _elapsed(self) -> float:
        return time.monotonic() - self._start

    def _check_fault(self) -> None:
        if self.args.fault != "sensor_rate_drop":
            return
        start = self.args.fault_start
        end = start + self.args.fault_duration
        elapsed = self._elapsed()
        self._scan_enabled = not (start <= elapsed <= end)
        if abs(elapsed - start) < 0.6:
            self.get_logger().info("Fault injected: sensor_rate_drop on /scan")

    def _publish_scan(self) -> None:
        if not self._scan_enabled:
            return
        msg = LaserScan()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "laser"
        msg.angle_min = -math.pi
        msg.angle_max = math.pi
        msg.angle_increment = math.pi / 180
        msg.range_min = 0.1
        msg.range_max = 10.0
        msg.ranges = [1.0] * 360
        self._scan_pub.publish(msg)

    def _publish_odom(self) -> None:
        msg = Odometry()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "odom"
        msg.child_frame_id = "base_link"
        self._odom_pub.publish(msg)

    def _publish_diagnostics(self) -> None:
        msg = DiagnosticArray()
        msg.header.stamp = self.get_clock().now().to_msg()
        status = DiagnosticStatus()
        status.name = "Battery"
        status.level = DiagnosticStatus.OK
        status.message = "Battery nominal"
        status.values = [KeyValue(key="charge", value="85%")]
        msg.status = [status]
        self._diag_pub.publish(msg)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="SwarmMon lightweight ROS 2 sim harness")
    p.add_argument("--scan-hz", type=float, default=10.0)
    p.add_argument("--odom-hz", type=float, default=30.0)
    p.add_argument("--diag-hz", type=float, default=1.0)
    p.add_argument("--fault", choices=["sensor_rate_drop"], default=None)
    p.add_argument("--fault-start", type=float, default=10.0, help="Seconds after start")
    p.add_argument("--fault-duration", type=float, default=5.0)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    rclpy.init()
    node = SimHarness(args)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
