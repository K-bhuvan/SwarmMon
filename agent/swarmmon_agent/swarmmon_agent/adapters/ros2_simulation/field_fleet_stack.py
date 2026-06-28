"""Mike field fleet — ROS gateway (+ optional local topic publisher for dev)."""

from __future__ import annotations

import argparse
import os
import sys

try:
    import rclpy
    from rclpy.executors import MultiThreadedExecutor

    from swarmmon_agent.adapters.ros2_simulation.fleet_gateway import FleetGateway
    from swarmmon_agent.adapters.ros2_simulation.fleet_status_publisher import (
        FleetStatusPublisher,
    )
except ImportError:
    print("ROS 2 (rclpy) required. Source your ROS 2 installation first.", file=sys.stderr)
    raise SystemExit(1) from None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="SwarmMon field fleet ROS stack")
    p.add_argument(
        "--dev",
        action="store_true",
        help="Also publish fleet status on /swarmmon/fleet/status (local dev without drones)",
    )
    p.add_argument(
        "--fleet-id",
        default=os.environ.get("SWARMMON_FLEET_ID", "mike-farm"),
    )
    p.add_argument(
        "--drone-count",
        type=int,
        default=int(os.environ.get("SWARMMON_DRONE_COUNT", "4")),
    )
    p.add_argument(
        "--interval",
        type=float,
        default=float(os.environ.get("SWARMMON_HEARTBEAT_INTERVAL", "30")),
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    rclpy.init()
    executor = MultiThreadedExecutor()
    nodes = [FleetGateway()]

    if args.dev:
        nodes.append(
            FleetStatusPublisher(
                fleet_id=args.fleet_id,
                drone_count=args.drone_count,
                interval_seconds=args.interval,
            )
        )

    for node in nodes:
        executor.add_node(node)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        for node in nodes:
            node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
